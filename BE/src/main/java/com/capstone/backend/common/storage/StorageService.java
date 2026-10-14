package com.capstone.backend.common.storage;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import java.util.Locale;
import java.util.Map;

/**
 * Supabase Storage 이미지 업로드.
 *
 * 형식(jpg/png/heic/webp)과 크기(10MB)는 여기서 검사한다. API마다 더 작은 상한이 있으면 호출하는 쪽에서 먼저 검사한다.
 */
@Slf4j
@Service
public class StorageService {

    public static final long MAX_FILE_SIZE = 10L * 1024 * 1024;

    /** 허용 MIME → 저장할 확장자 */
    private static final Map<String, String> EXTENSION_BY_CONTENT_TYPE = Map.of(
            "image/jpeg", "jpg",
            "image/jpg", "jpg",
            "image/png", "png",
            "image/heic", "heic",
            "image/webp", "webp"
    );

    /** Content-Type 이 없거나 octet-stream 일 때 파일 이름의 확장자로 판단한다 (iOS heic 가 이렇게 오는 경우가 있다) */
    private static final Map<String, String> CONTENT_TYPE_BY_EXTENSION = Map.of(
            "jpg", "image/jpeg",
            "jpeg", "image/jpeg",
            "png", "image/png",
            "heic", "image/heic",
            "webp", "image/webp"
    );

    private final WebClient webClient;
    private final String supabaseUrl;
    private final String supabaseServiceRoleKey;
    private final String supabaseStorageUrl;

    public StorageService(WebClient webClient,
                          @Value("${supabase.url}") String supabaseUrl,
                          @Value("${supabase.service-role-key}") String supabaseServiceRoleKey,
                          @Value("${supabase.storage-url}") String supabaseStorageUrl) {
        this.webClient = webClient;
        this.supabaseUrl = supabaseUrl;
        this.supabaseServiceRoleKey = supabaseServiceRoleKey;
        this.supabaseStorageUrl = supabaseStorageUrl;
    }

    /**
     * 이미지를 올리고 공개 URL을 돌려준다. 같은 경로에 이미 있으면 덮어쓴다.
     *
     * @param bucket Supabase Storage 버킷 (예: profile_image)
     * @param path   버킷 안 경로. 확장자 없이 넘기면 검사한 형식의 확장자를 붙인다 (예: {userId} → {userId}.png)
     */
    public String upload(String bucket, String path, MultipartFile file) {
        if (file == null || file.isEmpty()) {
            throw new BusinessException(ErrorCode.VALIDATION_ERROR);
        }
        if (file.getSize() > MAX_FILE_SIZE) {
            throw new BusinessException(ErrorCode.FILE_TOO_LARGE);
        }
        String contentType = resolveContentType(file);
        String objectPath = bucket + "/" + path + "." + EXTENSION_BY_CONTENT_TYPE.get(contentType);

        try {
            byte[] bytes = file.getBytes();
            String uploadUrl = supabaseStorageUrl + "/" + objectPath;
            log.info("[Storage] 업로드 시작: url={}, size={}, contentType={}", uploadUrl, bytes.length, contentType);

            webClient.post()
                    .uri(uploadUrl)
                    .header(HttpHeaders.AUTHORIZATION, "Bearer " + supabaseServiceRoleKey)
                    .header(HttpHeaders.CONTENT_TYPE, contentType)
                    .header("x-upsert", "true")
                    .bodyValue(bytes)
                    .retrieve()
                    .bodyToMono(String.class)
                    .block();

            String publicUrl = supabaseUrl + "/storage/v1/object/public/" + objectPath;
            log.info("[Storage] 업로드 성공: {}", publicUrl);
            return publicUrl;

        } catch (WebClientResponseException e) {
            log.error("[Storage] 업로드 실패: status={}, body={}", e.getStatusCode(), e.getResponseBodyAsString());
            throw new BusinessException(ErrorCode.INTERNAL_ERROR);
        } catch (Exception e) {
            log.error("[Storage] 업로드 예외: {}", e.getMessage(), e);
            throw new BusinessException(ErrorCode.INTERNAL_ERROR);
        }
    }

    /** 허용 형식이면 정규화한 MIME 을, 아니면 VALIDATION_ERROR 를 던진다 */
    private String resolveContentType(MultipartFile file) {
        String contentType = file.getContentType() == null ? "" : file.getContentType().toLowerCase(Locale.ROOT);
        if (EXTENSION_BY_CONTENT_TYPE.containsKey(contentType)) {
            return contentType.equals("image/jpg") ? "image/jpeg" : contentType;
        }
        if (contentType.isEmpty() || contentType.equals("application/octet-stream")) {
            String filename = file.getOriginalFilename();
            int dot = filename == null ? -1 : filename.lastIndexOf('.');
            if (dot >= 0) {
                String byExtension = CONTENT_TYPE_BY_EXTENSION.get(filename.substring(dot + 1).toLowerCase(Locale.ROOT));
                if (byExtension != null) {
                    return byExtension;
                }
            }
        }
        throw new BusinessException(ErrorCode.VALIDATION_ERROR);
    }
}
