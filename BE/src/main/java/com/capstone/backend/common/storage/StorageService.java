package com.capstone.backend.common.storage;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import io.netty.channel.ChannelOption;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.core.Exceptions;
import reactor.netty.http.client.HttpClient;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Arrays;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.TimeoutException;

/**
 * Supabase Storage 이미지 업로드.
 *
 * 형식(jpg/png/heic/webp)과 크기(10MB)는 여기서 검사한다. 형식은 클라이언트가 밝힌 값과 파일 서명이 모두 맞아야 받는다. API마다 더 작은 상한이 있으면 호출하는 쪽에서 먼저 검사한다.
 */
@Slf4j
@Service
public class StorageService {

    public static final long MAX_FILE_SIZE = 10L * 1024 * 1024;

    /** 허용 형식. 저장할 때의 MIME 과 확장자를 가진다 */
    enum ImageFormat {
        JPEG("image/jpeg", "jpg"),
        PNG("image/png", "png"),
        HEIC("image/heic", "heic"),
        WEBP("image/webp", "webp");

        final String contentType;
        final String extension;

        ImageFormat(String contentType, String extension) {
            this.contentType = contentType;
            this.extension = extension;
        }
    }

    /** 클라이언트가 보낸 Content-Type → 형식 */
    private static final Map<String, ImageFormat> FORMAT_BY_CONTENT_TYPE = Map.of(
            "image/jpeg", ImageFormat.JPEG,
            "image/jpg", ImageFormat.JPEG,
            "image/png", ImageFormat.PNG,
            "image/heic", ImageFormat.HEIC,
            "image/webp", ImageFormat.WEBP
    );

    /** Content-Type 이 없거나 octet-stream 일 때 파일 이름의 확장자로 판단한다 (iOS heic 가 이렇게 오는 경우가 있다) */
    private static final Map<String, ImageFormat> FORMAT_BY_EXTENSION = Map.of(
            "jpg", ImageFormat.JPEG,
            "jpeg", ImageFormat.JPEG,
            "png", ImageFormat.PNG,
            "heic", ImageFormat.HEIC,
            "webp", ImageFormat.WEBP
    );

    private static final byte[] JPEG_SIGNATURE = {(byte) 0xFF, (byte) 0xD8, (byte) 0xFF};
    private static final byte[] PNG_SIGNATURE = {(byte) 0x89, 'P', 'N', 'G', '\r', '\n', 0x1A, '\n'};

    /** HEIC 파일의 ftyp 박스에 오는 브랜드 */
    private static final Set<String> HEIC_BRANDS = Set.of(
            "heic", "heix", "hevc", "hevx", "heim", "heis", "hevm", "hevs", "mif1", "msf1");

    // Supabase 가 응답하지 않아도 요청 스레드를 오래 잡지 않도록 업로드에만 기한을 둔다.
    // 공용 WebClient 빈은 AI 호출도 함께 쓰므로 바꾸지 않고 mutate() 한 복사본에만 적용한다.
    private static final Duration CONNECT_TIMEOUT = Duration.ofSeconds(3);
    private static final Duration RESPONSE_TIMEOUT = Duration.ofSeconds(10);
    static final Duration UPLOAD_TIMEOUT = Duration.ofSeconds(15);

    private final WebClient webClient;
    private final String supabaseUrl;
    private final String supabaseServiceRoleKey;
    private final String supabaseStorageUrl;
    private final Duration uploadTimeout;

    @Autowired
    public StorageService(WebClient webClient,
                          @Value("${supabase.url}") String supabaseUrl,
                          @Value("${supabase.service-role-key}") String supabaseServiceRoleKey,
                          @Value("${supabase.storage-url}") String supabaseStorageUrl) {
        this(webClient, supabaseUrl, supabaseServiceRoleKey, supabaseStorageUrl, UPLOAD_TIMEOUT);
    }

    StorageService(WebClient webClient, String supabaseUrl, String supabaseServiceRoleKey,
                   String supabaseStorageUrl, Duration uploadTimeout) {
        HttpClient httpClient = HttpClient.create()
                .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, (int) CONNECT_TIMEOUT.toMillis())
                .responseTimeout(RESPONSE_TIMEOUT);
        this.webClient = webClient.mutate()
                .clientConnector(new ReactorClientHttpConnector(httpClient))
                .build();
        this.supabaseUrl = supabaseUrl;
        this.supabaseServiceRoleKey = supabaseServiceRoleKey;
        this.supabaseStorageUrl = supabaseStorageUrl;
        this.uploadTimeout = uploadTimeout;
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
        ImageFormat declared = declaredFormat(file);
        byte[] bytes = readBytes(file);
        // Content-Type·파일 이름은 클라이언트가 정하는 값이라 믿지 않는다. 파일 앞부분의 서명으로 실제 형식을 확인한다
        ImageFormat actual = detectFormat(bytes);
        if (actual != declared) {
            log.warn("[Storage] 형식 불일치: declared={}, actual={}, contentType={}, filename={}",
                    declared, actual, file.getContentType(), file.getOriginalFilename());
            throw new BusinessException(ErrorCode.VALIDATION_ERROR);
        }
        String contentType = actual.contentType;
        String objectPath = bucket + "/" + path + "." + actual.extension;

        try {
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
                    .timeout(uploadTimeout)   // 연결·응답 기한과 별개로 업로드 전체에 거는 상한
                    .block();

            String publicUrl = supabaseUrl + "/storage/v1/object/public/" + objectPath;
            log.info("[Storage] 업로드 성공: {}", publicUrl);
            return publicUrl;

        } catch (WebClientResponseException e) {
            log.error("[Storage] 업로드 실패: status={}, body={}", e.getStatusCode(), e.getResponseBodyAsString());
            throw new BusinessException(ErrorCode.INTERNAL_ERROR);
        } catch (Exception e) {
            if (Exceptions.unwrap(e) instanceof TimeoutException) {
                log.error("[Storage] 업로드 시간 초과: {}초", uploadTimeout.toSeconds());
                throw new BusinessException(ErrorCode.INTERNAL_ERROR);
            }
            log.error("[Storage] 업로드 예외: {}", e.getMessage(), e);
            throw new BusinessException(ErrorCode.INTERNAL_ERROR);
        }
    }

    /** 클라이언트가 밝힌 형식. 허용 형식이 아니면 VALIDATION_ERROR 를 던진다 */
    private ImageFormat declaredFormat(MultipartFile file) {
        String contentType = file.getContentType() == null ? "" : file.getContentType().toLowerCase(Locale.ROOT);
        ImageFormat byContentType = FORMAT_BY_CONTENT_TYPE.get(contentType);
        if (byContentType != null) {
            return byContentType;
        }
        if (contentType.isEmpty() || contentType.equals("application/octet-stream")) {
            String filename = file.getOriginalFilename();
            int dot = filename == null ? -1 : filename.lastIndexOf('.');
            if (dot >= 0) {
                ImageFormat byExtension = FORMAT_BY_EXTENSION.get(filename.substring(dot + 1).toLowerCase(Locale.ROOT));
                if (byExtension != null) {
                    return byExtension;
                }
            }
        }
        throw new BusinessException(ErrorCode.VALIDATION_ERROR);
    }

    /** 파일 서명(매직 바이트)으로 판단한 실제 형식. 허용 형식이 아니면 null */
    static ImageFormat detectFormat(byte[] bytes) {
        if (startsWith(bytes, 0, JPEG_SIGNATURE)) {
            return ImageFormat.JPEG;
        }
        if (startsWith(bytes, 0, PNG_SIGNATURE)) {
            return ImageFormat.PNG;
        }
        // WebP: "RIFF" + 크기 4바이트 + "WEBP"
        if (startsWith(bytes, 0, ascii("RIFF")) && startsWith(bytes, 8, ascii("WEBP"))) {
            return ImageFormat.WEBP;
        }
        // HEIC: 크기 4바이트 + "ftyp" + 브랜드 4바이트
        if (startsWith(bytes, 4, ascii("ftyp")) && bytes.length >= 12
                && HEIC_BRANDS.contains(new String(bytes, 8, 4, StandardCharsets.US_ASCII))) {
            return ImageFormat.HEIC;
        }
        return null;
    }

    private static boolean startsWith(byte[] bytes, int offset, byte[] prefix) {
        if (bytes.length < offset + prefix.length) {
            return false;
        }
        return Arrays.equals(bytes, offset, offset + prefix.length, prefix, 0, prefix.length);
    }

    private static byte[] ascii(String s) {
        return s.getBytes(StandardCharsets.US_ASCII);
    }

    private static byte[] readBytes(MultipartFile file) {
        try {
            return file.getBytes();
        } catch (IOException e) {
            log.error("[Storage] 업로드 파일 읽기 실패: {}", e.getMessage(), e);
            throw new BusinessException(ErrorCode.INTERNAL_ERROR);
        }
    }
}
