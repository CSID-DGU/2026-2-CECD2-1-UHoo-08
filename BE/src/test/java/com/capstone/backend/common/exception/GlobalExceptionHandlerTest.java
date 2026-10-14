package com.capstone.backend.common.exception;

import com.capstone.backend.common.response.ApiResponse;
import org.junit.jupiter.api.Test;
import org.springframework.http.ResponseEntity;
import org.springframework.web.multipart.MaxUploadSizeExceededException;

import static org.assertj.core.api.Assertions.assertThat;

class GlobalExceptionHandlerTest {

    @Test
    void multipart_상한을_넘은_업로드는_413_FILE_TOO_LARGE로_응답한다() {
        ResponseEntity<ApiResponse<Void>> response = new GlobalExceptionHandler()
                .handleMaxUploadSizeExceededException(new MaxUploadSizeExceededException(10L * 1024 * 1024));

        assertThat(response.getStatusCode().value()).isEqualTo(413);
        assertThat(response.getBody().getError().getCode()).isEqualTo("FILE_TOO_LARGE");
    }
}
