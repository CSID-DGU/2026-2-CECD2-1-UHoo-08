package com.capstone.backend.common.storage;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.storage.StorageService.ImageFormat;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.web.reactive.function.client.ClientRequest;
import org.springframework.web.reactive.function.client.ClientResponse;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.junit.jupiter.api.Assertions.assertTimeoutPreemptively;

class StorageServiceTest {

    private static final String SUPABASE_URL = "https://test.supabase.co";

    private final List<ClientRequest> requests = new ArrayList<>();
    private HttpStatus storageStatus = HttpStatus.OK;

    // Supabase 대신 요청만 기록하고 storageStatus 로 응답하는 WebClient
    private final StorageService storageService = new StorageService(
            WebClient.builder()
                    .exchangeFunction(request -> {
                        requests.add(request);
                        return Mono.just(ClientResponse.create(storageStatus).body("{}").build());
                    })
                    .build(),
            SUPABASE_URL,
            "service-key",
            SUPABASE_URL + "/storage/v1/object");

    /** 형식별 파일 서명으로 시작하는 size 바이트짜리 내용 */
    private static byte[] image(String format, int size) {
        byte[] header = switch (format) {
            case "jpg" -> new byte[]{(byte) 0xFF, (byte) 0xD8, (byte) 0xFF, (byte) 0xE0};
            case "png" -> new byte[]{(byte) 0x89, 'P', 'N', 'G', '\r', '\n', 0x1A, '\n'};
            case "webp" -> ascii("RIFF\0\0\0\0WEBPVP8 ");
            case "heic" -> ascii("\0\0\0\u0018ftypheic");
            case "gif" -> ascii("GIF89a");
            case "pdf" -> ascii("%PDF-1.7");
            default -> ascii("hello, not an image");
        };
        return Arrays.copyOf(header, Math.max(size, header.length));
    }

    private static byte[] image(String format) {
        return image(format, 32);
    }

    private static byte[] ascii(String s) {
        return s.getBytes(StandardCharsets.ISO_8859_1);
    }

    @Test
    void 업로드하면_공개_URL을_돌려주고_Storage에_덮어쓰기로_올린다() {
        MockMultipartFile file = new MockMultipartFile("image", "a.png", "image/png", image("png"));

        String url = storageService.upload("profile_image", "user-1", file);

        assertThat(url).isEqualTo(SUPABASE_URL + "/storage/v1/object/public/profile_image/user-1.png");
        assertThat(requests).hasSize(1);
        ClientRequest request = requests.get(0);
        assertThat(request.url().toString()).isEqualTo(SUPABASE_URL + "/storage/v1/object/profile_image/user-1.png");
        assertThat(request.headers().getFirst(HttpHeaders.AUTHORIZATION)).isEqualTo("Bearer service-key");
        assertThat(request.headers().getFirst(HttpHeaders.CONTENT_TYPE)).isEqualTo("image/png");
        assertThat(request.headers().getFirst("x-upsert")).isEqualTo("true");
    }

    @ParameterizedTest
    @CsvSource({
            "image/jpeg, a.jpg, jpg, image/jpeg",
            "image/jpg, a.jpg, jpg, image/jpeg",
            "IMAGE/PNG, a.png, png, image/png",
            "image/heic, a.heic, heic, image/heic",
            "image/webp, a.webp, webp, image/webp",
            // Content-Type 이 없거나 octet-stream 이면 파일 이름의 확장자로 판단한다
            "application/octet-stream, IMG_0001.HEIC, heic, image/heic",
            "'', photo.jpeg, jpg, image/jpeg",
    })
    void 허용_형식은_형식에_맞는_확장자로_저장한다(String contentType, String filename, String ext, String sentType) {
        MockMultipartFile file = new MockMultipartFile("image", filename, contentType, image(ext));

        String url = storageService.upload("bucket", "obj", file);

        assertThat(url).endsWith("/bucket/obj." + ext);
        assertThat(requests.get(0).headers().getFirst(HttpHeaders.CONTENT_TYPE)).isEqualTo(sentType);
    }

    @ParameterizedTest
    @CsvSource({
            "image/gif, a.gif",
            "application/pdf, a.pdf",
            "application/octet-stream, a.gif",
            "application/octet-stream, noext",
    })
    void 허용하지_않는_형식은_VALIDATION_ERROR이고_올리지_않는다(String contentType, String filename) {
        MockMultipartFile file = new MockMultipartFile("image", filename, contentType, image("gif"));

        assertThatThrownBy(() -> storageService.upload("bucket", "obj", file))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.VALIDATION_ERROR);
        assertThat(requests).isEmpty();
    }

    @ParameterizedTest
    @CsvSource({
            // 이미지가 아닌 내용에 허용 형식의 Content-Type·파일 이름을 붙인 경우
            "image/png, a.png, text",
            "image/jpeg, a.jpg, pdf",
            "application/octet-stream, a.heic, gif",
            // 허용 형식끼리라도 밝힌 형식과 실제 내용이 다르면 거절한다
            "image/png, a.png, jpg",
            "image/heic, a.heic, webp",
    })
    void 파일_서명이_밝힌_형식과_다르면_VALIDATION_ERROR이고_올리지_않는다(String contentType, String filename,
                                                          String actual) {
        MockMultipartFile file = new MockMultipartFile("image", filename, contentType, image(actual));

        assertThatThrownBy(() -> storageService.upload("bucket", "obj", file))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.VALIDATION_ERROR);
        assertThat(requests).isEmpty();
    }

    @ParameterizedTest
    @CsvSource({"jpg, JPEG", "png, PNG", "webp, WEBP", "heic, HEIC"})
    void 파일_서명으로_형식을_판단한다(String format, ImageFormat expected) {
        assertThat(StorageService.detectFormat(image(format))).isEqualTo(expected);
    }

    @ParameterizedTest
    @ValueSource(strings = {"heix", "hevc", "mif1", "msf1"})
    void HEIC는_ftyp_박스의_브랜드로_판단한다(String brand) {
        assertThat(StorageService.detectFormat(ascii("\0\0\0\u0018ftyp" + brand + "\0\0\0\0")))
                .isEqualTo(ImageFormat.HEIC);
    }

    @Test
    void 서명이_없거나_짧은_내용은_형식을_판단하지_않는다() {
        assertThat(StorageService.detectFormat(new byte[]{(byte) 0xFF, (byte) 0xD8})).isNull();
        assertThat(StorageService.detectFormat(ascii("RIFF\0\0\0\0WAVE"))).isNull();
        assertThat(StorageService.detectFormat(ascii("\0\0\0\u0018ftypavif"))).isNull();
        assertThat(StorageService.detectFormat(image("gif"))).isNull();
    }

    @Test
    void 빈_파일은_VALIDATION_ERROR다() {
        MockMultipartFile file = new MockMultipartFile("image", "a.png", "image/png", new byte[0]);

        assertThatThrownBy(() -> storageService.upload("bucket", "obj", file))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.VALIDATION_ERROR);
    }

    @Test
    void 크기가_10MB를_넘으면_FILE_TOO_LARGE이고_올리지_않는다() {
        MockMultipartFile limit = new MockMultipartFile("image", "a.png", "image/png",
                image("png", (int) StorageService.MAX_FILE_SIZE));
        MockMultipartFile over = new MockMultipartFile("image", "a.png", "image/png",
                image("png", (int) StorageService.MAX_FILE_SIZE + 1));

        storageService.upload("bucket", "obj", limit);
        assertThatThrownBy(() -> storageService.upload("bucket", "obj", over))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.FILE_TOO_LARGE);
        assertThat(requests).hasSize(1);
    }

    @Test
    void Storage가_에러를_주면_INTERNAL_ERROR다() {
        storageStatus = HttpStatus.BAD_REQUEST;
        MockMultipartFile file = new MockMultipartFile("image", "a.png", "image/png", image("png"));

        assertThatThrownBy(() -> storageService.upload("bucket", "obj", file))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.INTERNAL_ERROR);
    }

    @Test
    void Storage가_응답하지_않으면_기한이_지나_INTERNAL_ERROR다() {
        // 응답을 영원히 주지 않는 Storage. 기한이 없으면 block() 에서 멈춘다
        StorageService hanging = new StorageService(
                WebClient.builder().exchangeFunction(request -> Mono.never()).build(),
                SUPABASE_URL, "service-key", SUPABASE_URL + "/storage/v1/object",
                Duration.ofMillis(200));
        MockMultipartFile file = new MockMultipartFile("image", "a.png", "image/png", image("png"));

        assertTimeoutPreemptively(Duration.ofSeconds(5), () ->
                assertThatThrownBy(() -> hanging.upload("bucket", "obj", file))
                        .isInstanceOf(BusinessException.class)
                        .extracting("errorCode").isEqualTo(ErrorCode.INTERNAL_ERROR));
    }

    @Test
    void 운영_업로드_기한은_15초다() {
        assertThat(StorageService.UPLOAD_TIMEOUT).isEqualTo(Duration.ofSeconds(15));
    }
}
