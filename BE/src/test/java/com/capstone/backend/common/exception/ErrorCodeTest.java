package com.capstone.backend.common.exception;

import com.capstone.backend.common.response.ApiResponse;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.springframework.http.ResponseEntity;

import java.util.Arrays;

import static org.assertj.core.api.Assertions.assertThat;

class ErrorCodeTest {

    @ParameterizedTest
    @CsvSource({
            "CLARIFY_NOT_REQUIRED, 409, 되묻기가 필요한 상태가 아닙니다",
            "RECOGNITION_NOT_FOUND, 404, 사진 인식 결과가 없거나 만료되었습니다",
            "USER_PRODUCT_NOT_FOUND, 404, 보유 제품을 찾을 수 없습니다",
            "REGION_NOT_SET, 404, 지역을 먼저 설정해주세요",
            "BUNDLE_OVER_BUDGET, 422, 교체하면 예산을 넘습니다",
            "CHANGE_NOT_REVERTIBLE, 409, 되돌릴 수 없는 변경입니다",
    })
    void 신규_에러_코드는_명세의_상태와_메시지를_가진다(String name, int status, String message) {
        ErrorCode errorCode = ErrorCode.valueOf(name);

        assertThat(errorCode.getStatus().value()).isEqualTo(status);
        assertThat(errorCode.getMessage()).isEqualTo(message);
    }

    @Test
    void 응답에_나가는_code는_enum_이름과_같다() {
        assertThat(ErrorCode.values())
                .allSatisfy(errorCode -> assertThat(errorCode.getCode()).isEqualTo(errorCode.name()));
    }

    @Test
    void 개인화_제안_API를_빼면서_SUGGESTION_NOT_FOUND는_두지_않는다() {
        assertThat(Arrays.stream(ErrorCode.values()).map(Enum::name))
                .doesNotContain("SUGGESTION_NOT_FOUND");
    }

    @Test
    void BusinessException으로_던지면_코드의_상태와_에러_본문으로_응답한다() {
        ResponseEntity<ApiResponse<Void>> response = new GlobalExceptionHandler()
                .handleBusinessException(new BusinessException(ErrorCode.BUNDLE_OVER_BUDGET));

        assertThat(response.getStatusCode().value()).isEqualTo(422);
        ApiResponse<Void> body = response.getBody();
        assertThat(body.isSuccess()).isFalse();
        assertThat(body.getError().getCode()).isEqualTo("BUNDLE_OVER_BUDGET");
        assertThat(body.getError().getMessage()).isEqualTo("교체하면 예산을 넘습니다");
        assertThat(body.getError().getStatus()).isEqualTo(422);
    }
}
