package com.capstone.backend.domain.product.service;

import com.capstone.backend.common.ai.AiInternalClient;
import com.capstone.backend.common.ai.dto.AiInternalDtos.ProductCandidate;
import com.capstone.backend.common.ai.dto.AiInternalDtos.RecognizePhotosRequest;
import com.capstone.backend.common.ai.dto.AiInternalDtos.RecognizePhotosResponse;
import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.storage.StorageService;
import com.capstone.backend.common.util.JsonUtil;
import com.capstone.backend.domain.product.dto.response.ExpiryRecognitionResponse;
import com.capstone.backend.domain.product.dto.response.ExpiryRecognitionResponse.ReadValue;
import com.capstone.backend.domain.product.dto.response.PhotoRecognitionResponse;
import com.capstone.backend.domain.product.dto.response.PhotoRecognitionResponse.Candidate;
import com.capstone.backend.domain.product.entity.PhotoRecognition;
import com.capstone.backend.domain.product.repository.PhotoRecognitionRepository;
import com.fasterxml.jackson.core.type.TypeReference;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.time.Duration;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.format.DateTimeParseException;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * 사진으로 보유 제품을 등록할 때의 인식 단계.
 *
 * 제품명 사진 → 기한 사진 → 등록은 서로 다른 요청이라, 인식 결과를 photo_recognitions 에 잠시 남겨 두고
 * recognitionId 로 잇는다. 서버가 여러 대여도 이어지도록 메모리가 아닌 DB 에 둔다.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class PhotoRecognitionService {

    static final String BUCKET = "user-product-photos";
    static final Duration VALID_FOR = Duration.ofMinutes(30);
    static final int MAX_CANDIDATES = 3;

    /** 응답 원본에서 기한 사진 인식의 원본을 담는 키. 제품명 사진의 원본은 그대로 두고 옆에 붙인다 */
    static final String EXPIRY_RAW_KEY = "expiry";

    /** AI 응답 원본에서 읽은 글자가 들어 있을 수 있는 키. AI 계약에 아직 전용 필드가 없다 */
    private static final List<String> READ_TEXT_KEYS = List.of("readText", "text");

    private final StorageService storageService;
    private final AiInternalClient aiInternalClient;
    private final PhotoRecognitionRepository photoRecognitionRepository;
    private final JsonUtil jsonUtil;

    /** 제품명 사진을 올리고 후보를 찾는다. 후보가 없어도 실패가 아니다(화면이 이름 검색으로 안내한다) */
    public PhotoRecognitionResponse recognizeName(UUID userId, MultipartFile image) {
        String nameImageUrl = storageService.upload(BUCKET, userId + "/" + UUID.randomUUID(), image);

        RecognizePhotosResponse result = callAi(new RecognizePhotosRequest(nameImageUrl, null));
        List<Candidate> candidates = toCandidates(result.candidates());
        String readText = readTextOf(result.raw());

        PhotoRecognition saved = photoRecognitionRepository.save(PhotoRecognition.builder()
                .userId(userId)
                .nameImageUrl(nameImageUrl)
                .readText(readText)
                .candidates(jsonUtil.write(candidates))
                .raw(jsonUtil.write(result.raw() == null ? Map.of() : result.raw()))
                .expiresAt(OffsetDateTime.now().plus(VALID_FOR))
                .build());

        return new PhotoRecognitionResponse(saved.getId(), readText, candidates);
    }

    /**
     * 뒷면·바닥 사진에서 유통기한, 개봉 후 사용 기간, 제조일을 읽는다.
     * 읽지 못한 값은 NOT_READ 로 두고 채우지 않는다. 잘못 채운 기한은 사용자가 확인하지 않고 넘겨 그대로 소진 알림이 된다.
     */
    public ExpiryRecognitionResponse recognizeExpiry(UUID userId, UUID recognitionId, MultipartFile image) {
        // 업로드 전에 확인해, 쓸 수 없는 인식 결과에 사진이 올라가지 않게 한다
        PhotoRecognition recognition = photoRecognitionRepository.findById(recognitionId)
                .filter(r -> r.isUsableBy(userId, OffsetDateTime.now()))
                .orElseThrow(() -> new BusinessException(ErrorCode.RECOGNITION_NOT_FOUND));

        String dateImageUrl = storageService.upload(BUCKET, userId + "/" + UUID.randomUUID(), image);
        RecognizePhotosResponse result = requestExpiry(recognition.getNameImageUrl(), dateImageUrl);

        String expiryDate = dateOrNull(result.expiryDate(), "expiryDate");
        Integer paoMonths = result.paoMonths() != null && result.paoMonths() > 0 ? result.paoMonths() : null;
        String manufacturedAt = dateOrNull(result.mfgDate(), "mfgDate");

        Map<String, Object> expiryResult = new LinkedHashMap<>();
        expiryResult.put("expiryDate", expiryDate);
        expiryResult.put("paoMonths", paoMonths);
        expiryResult.put("manufacturedAt", manufacturedAt);
        recognition.recordExpiry(dateImageUrl, jsonUtil.write(expiryResult), mergeRaw(recognition.getRaw(), result.raw()));
        photoRecognitionRepository.save(recognition);

        return new ExpiryRecognitionResponse(
                ReadValue.of(expiryDate), ReadValue.of(paoMonths), ReadValue.of(manufacturedAt));
    }

    /**
     * 기한을 읽는 AI 호출. 지금 AI 계약은 두 장을 한 번에 받아서, 저장해 둔 제품명 사진과 새 기한 사진을 같이 보내고 기한 값만 쓴다.
     * 기한만 받는 AI 경로가 생기면 여기만 바꾼다.
     */
    private RecognizePhotosResponse requestExpiry(String nameImageUrl, String dateImageUrl) {
        return callAi(new RecognizePhotosRequest(nameImageUrl, dateImageUrl));
    }

    private RecognizePhotosResponse callAi(RecognizePhotosRequest request) {
        RecognizePhotosResponse result;
        try {
            result = aiInternalClient.recognizePhotos(request);
        } catch (Exception e) {
            // 사용자에게는 IMAGE_PARSE_FAILED 만 나가므로 원인은 여기서 스택과 함께 남긴다
            log.error("[PhotoRecognition] AI 사진 인식 실패: type={}, message={}",
                    e.getClass().getSimpleName(), e.getMessage(), e);
            throw new BusinessException(ErrorCode.IMAGE_PARSE_FAILED);
        }
        if (result == null) {
            log.error("[PhotoRecognition] AI 사진 인식 응답이 비어 있다");
            throw new BusinessException(ErrorCode.IMAGE_PARSE_FAILED);
        }
        if (result.stub()) {
            log.warn("[PhotoRecognition] AI 사진 인식은 아직 stub 이다. 후보와 기한 없이 돌려준다");
            return new RecognizePhotosResponse(List.of(), null, null, null, result.raw(), true);
        }
        return result;
    }

    /** AI 후보를 일치도 높은 순으로 최대 3개, 일치도는 0~100 정수로 바꾼다 */
    static List<Candidate> toCandidates(List<ProductCandidate> aiCandidates) {
        if (aiCandidates == null) {
            return List.of();
        }
        return aiCandidates.stream()
                .sorted(Comparator.comparingDouble(ProductCandidate::confidence).reversed())
                .limit(MAX_CANDIDATES)
                .map(c -> new Candidate(c.productId(), c.name(), c.brand(), null, c.imageUrl(),
                        toMatchScore(c.confidence())))
                .toList();
    }

    static int toMatchScore(double confidence) {
        long score = Math.round(confidence * 100);
        return (int) Math.max(0, Math.min(100, score));
    }

    /** YYYY-MM-DD 가 아니면 읽지 못한 것으로 본다 */
    static String dateOrNull(String value, String field) {
        if (value == null || value.isBlank()) {
            return null;
        }
        try {
            return LocalDate.parse(value).toString();
        } catch (DateTimeParseException e) {
            log.warn("[PhotoRecognition] AI 가 돌려준 {} 값이 날짜 형식이 아니라 읽지 못한 것으로 둔다", field);
            return null;
        }
    }

    /** 제품명 사진의 원본은 두고 기한 사진의 원본을 옆에 붙인다. 등록할 때 둘 다 user_products.recognized_raw 로 간다 */
    private String mergeRaw(String savedRaw, Map<String, Object> expiryRaw) {
        Map<String, Object> saved = jsonUtil.read(savedRaw, new TypeReference<Map<String, Object>>() {
        });
        Map<String, Object> merged = saved == null ? new HashMap<>() : new HashMap<>(saved);
        merged.put(EXPIRY_RAW_KEY, expiryRaw == null ? Map.of() : expiryRaw);
        return jsonUtil.write(merged);
    }

    /** 읽은 글자를 응답 원본에서 꺼낸다. 없으면 빈 문자열 */
    static String readTextOf(Map<String, Object> raw) {
        if (raw == null) {
            return "";
        }
        for (String key : READ_TEXT_KEYS) {
            if (raw.get(key) instanceof String text) {
                return text;
            }
        }
        return "";
    }
}
