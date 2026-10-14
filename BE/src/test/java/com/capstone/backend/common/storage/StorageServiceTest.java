package com.capstone.backend.common.storage;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.web.reactive.function.client.ClientRequest;
import org.springframework.web.reactive.function.client.ClientResponse;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.util.ArrayList;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

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

    @Test
    void 업로드하면_공개_URL을_돌려주고_Storage에_덮어쓰기로_올린다() {
        MockMultipartFile file = new MockMultipartFile("image", "a.png", "image/png", new byte[]{1, 2, 3});

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
        MockMultipartFile file = new MockMultipartFile("image", filename, contentType, new byte[]{1});

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
        MockMultipartFile file = new MockMultipartFile("image", filename, contentType, new byte[]{1});

        assertThatThrownBy(() -> storageService.upload("bucket", "obj", file))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.VALIDATION_ERROR);
        assertThat(requests).isEmpty();
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
                new byte[(int) StorageService.MAX_FILE_SIZE]);
        MockMultipartFile over = new MockMultipartFile("image", "a.png", "image/png",
                new byte[(int) StorageService.MAX_FILE_SIZE + 1]);

        storageService.upload("bucket", "obj", limit);
        assertThatThrownBy(() -> storageService.upload("bucket", "obj", over))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.FILE_TOO_LARGE);
        assertThat(requests).hasSize(1);
    }

    @Test
    void Storage가_에러를_주면_INTERNAL_ERROR다() {
        storageStatus = HttpStatus.BAD_REQUEST;
        MockMultipartFile file = new MockMultipartFile("image", "a.png", "image/png", new byte[]{1});

        assertThatThrownBy(() -> storageService.upload("bucket", "obj", file))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.INTERNAL_ERROR);
    }
}
