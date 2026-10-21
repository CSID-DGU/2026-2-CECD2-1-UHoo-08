package com.capstone.backend.domain.product.controller;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.response.ApiResponse;
import com.capstone.backend.domain.product.dto.request.UserProductCreateRequest;
import com.capstone.backend.domain.product.dto.request.UserProductUpdateRequest;
import com.capstone.backend.domain.product.dto.response.ExpiryRecognitionResponse;
import com.capstone.backend.domain.product.dto.response.PhotoRecognitionResponse;
import com.capstone.backend.domain.product.dto.response.UserProductCreateResponse;
import com.capstone.backend.domain.product.dto.response.UserProductListResponse;
import com.capstone.backend.domain.product.dto.response.UserProductUpdateResponse;
import com.capstone.backend.domain.product.enums.UserProductFilter;
import com.capstone.backend.domain.product.enums.UserProductSort;
import com.capstone.backend.domain.product.service.PhotoRecognitionService;
import com.capstone.backend.domain.product.service.UserProductService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.util.Locale;
import java.util.UUID;

@RestController
@RequiredArgsConstructor
@Tag(name = "10. User Products", description = "보유 제품 API")
public class UserProductController {

    private final PhotoRecognitionService photoRecognitionService;
    private final UserProductService userProductService;

    private static final int MAX_PAGE_SIZE = 100;

    @Operation(
            summary = "보유 제품 등록",
            description = "고른 제품을 쓰는 중인 보유 제품으로 등록한다. 같은 제품을 이미 쓰는 중이면 409 ALREADY_REGISTERED. " +
                    "예전에 다 쓴 제품은 새 기록으로 다시 등록된다. recognitionId 를 보내면 사진 인식 원본을 함께 남긴다. " +
                    "openedAt 이 없으면 오늘. conflicts 는 성분 궁합 확인이 연결되기 전까지 빈 배열."
    )
    @PostMapping("/user-products")
    public ResponseEntity<ApiResponse<UserProductCreateResponse>> create(
            @AuthenticationPrincipal UUID userId,
            @Valid @RequestBody UserProductCreateRequest request) {
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(ApiResponse.success(userProductService.create(userId, request)));
    }

    @Operation(
            summary = "보유 제품 목록 조회",
            description = "status: USING(기본, 쓰는 중), FINISHED(다 쓰거나 버린 제품), ALL. " +
                    "sort: REPLACE_NEED(기본, 기한 지남 → 곧 교체 → 괜찮음, 같은 상태는 경과 비율순), RECENT(최근 등록순). " +
                    "page 는 1부터. 교체 시기는 유통기한과 개봉 후 사용 기간 중 이른 날로 계산한다. " +
                    "conflictText, conflictSummary 는 루틴 점검 결과가 연결되기 전까지 null 과 avoidCount=0."
    )
    @GetMapping("/user-products")
    public ResponseEntity<ApiResponse<UserProductListResponse>> list(
            @AuthenticationPrincipal UUID userId,
            @RequestParam(defaultValue = "USING") String status,
            @RequestParam(defaultValue = "REPLACE_NEED") String sort,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size) {
        if (page < 1 || size < 1 || size > MAX_PAGE_SIZE) {
            throw new BusinessException(ErrorCode.VALIDATION_ERROR);
        }
        UserProductListResponse result = userProductService.list(userId,
                parse(UserProductFilter.class, status), parse(UserProductSort.class, sort), page, size);
        return ResponseEntity.ok(ApiResponse.success(result, new ApiResponse.Meta(page, size, result.getTotal())));
    }

    @Operation(
            summary = "보유 제품 수정",
            description = "보낸 필드만 바꾸고 null 이거나 보내지 않은 필드는 그대로 둔다. " +
                    "'모두 사용' = status FINISHED (다 쓴 날 오늘), '진작 다 씀' = status FINISHED + finishedAt. 다 쓰면 remainingPct 는 0. " +
                    "status USING 으로 되돌릴 때 같은 제품을 쓰는 중인 다른 통이 있으면 409 ALREADY_REGISTERED. " +
                    "없거나 내 것이 아니면 404 USER_PRODUCT_NOT_FOUND."
    )
    @PatchMapping("/user-products/{userProductId}")
    public ResponseEntity<ApiResponse<UserProductUpdateResponse>> update(
            @AuthenticationPrincipal UUID userId,
            @PathVariable UUID userProductId,
            @Valid @RequestBody UserProductUpdateRequest request) {
        return ResponseEntity.ok(ApiResponse.success(userProductService.update(userId, userProductId, request)));
    }

    @Operation(
            summary = "제품명 사진 인식",
            description = "제품 앞면 사진에서 글자를 읽고 상품 후보를 일치도순으로 최대 3개 돌려준다. 후보가 없어도 200. " +
                    "recognitionId 는 30분 동안 유효하며 기한 사진 인식·보유 제품 등록에 쓴다. " +
                    "jpg/png/heic/webp, 최대 10MB."
    )
    @PostMapping(value = "/user-products/recognitions", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<ApiResponse<PhotoRecognitionResponse>> recognizeName(
            @AuthenticationPrincipal UUID userId,
            // 파일이 없을 때 스프링 기본 오류(500) 대신 업로드 검사의 VALIDATION_ERROR 로 응답하도록 필수로 두지 않는다
            @RequestPart(value = "image", required = false) MultipartFile image) {
        return ResponseEntity.ok(ApiResponse.success(photoRecognitionService.recognizeName(userId, image)));
    }

    @Operation(
            summary = "기한 사진 인식",
            description = "뒷면, 바닥 사진에서 유통기한, 개봉 후 사용 기간(개월), 제조일을 읽는다. " +
                    "읽지 못한 항목은 value=null, status=NOT_READ 로 오고 추측값은 채우지 않는다. " +
                    "recognitionId 가 없거나, 내 것이 아니거나, 만료(30분)됐으면 404 RECOGNITION_NOT_FOUND."
    )
    @PostMapping(value = "/user-products/recognitions/{recognitionId}/expiry", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<ApiResponse<ExpiryRecognitionResponse>> recognizeExpiry(
            @AuthenticationPrincipal UUID userId,
            @PathVariable String recognitionId,
            @RequestPart(value = "image", required = false) MultipartFile image) {
        return ResponseEntity.ok(ApiResponse.success(
                photoRecognitionService.recognizeExpiry(userId, toRecognitionId(recognitionId), image)));
    }

    // UUID 로 받으면 형식이 틀린 ID 가 스프링 기본 오류(500)로 나간다. 없는 인식 결과와 같게 404 로 응답한다
    private static UUID toRecognitionId(String recognitionId) {
        try {
            return UUID.fromString(recognitionId);
        } catch (IllegalArgumentException e) {
            throw new BusinessException(ErrorCode.RECOGNITION_NOT_FOUND);
        }
    }

    // enum 으로 받으면 모르는 값이 스프링 기본 오류(500)로 나간다. 요청 파라미터 오류로 응답한다
    private static <E extends Enum<E>> E parse(Class<E> type, String value) {
        try {
            return Enum.valueOf(type, value.toUpperCase(Locale.ROOT));
        } catch (IllegalArgumentException e) {
            throw new BusinessException(ErrorCode.VALIDATION_ERROR);
        }
    }
}
