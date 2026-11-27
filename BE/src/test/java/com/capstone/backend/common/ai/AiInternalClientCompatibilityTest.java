package com.capstone.backend.common.ai;

import com.capstone.backend.common.ai.dto.AiInternalDtos.CompatibilityCheckResponse;
import com.capstone.backend.domain.home.enums.CompatibilityLevel;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.mock.http.client.reactive.MockClientHttpRequest;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.web.reactive.function.client.ClientRequest;
import org.springframework.web.reactive.function.client.ClientResponse;
import org.springframework.web.reactive.function.client.ExchangeFunction;
import org.springframework.web.reactive.function.client.ExchangeStrategies;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.assertThat;

@ExtendWith(OutputCaptureExtension.class)
class AiInternalClientCompatibilityTest {

    private static final Duration SHORT_TIMEOUT = Duration.ofMillis(100);

    private final UUID userId = UUID.randomUUID();
    private final UUID productId = UUID.randomUUID();

    private AiInternalClient client(ExchangeFunction exchange) {
        AiInternalClient client = new AiInternalClient(WebClient.builder().exchangeFunction(exchange).build());
        ReflectionTestUtils.setField(client, "aiServerUrl", "http://ai");
        return client;
    }

    private static ExchangeFunction respond(HttpStatus status, String body) {
        return request -> Mono.just(ClientResponse.create(status)
                .header(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                .body(body)
                .build());
    }

    private static void assertDefault(CompatibilityCheckResponse response) {
        assertThat(response.level()).isEqualTo(CompatibilityLevel.OK);
        assertThat(response.pairs()).isEmpty();
        assertThat(response.stub()).isFalse();
    }

    @Test
    void 정상_응답을_읽고_사용자와_상품을_보낸다() throws Exception {
        String fixture = Files.readString(Path.of("..", "docs", "internal-api-fixtures", "compatibility-check.response.json"));
        AtomicReference<ClientRequest> sent = new AtomicReference<>();
        ExchangeFunction ok = respond(HttpStatus.OK, fixture);

        CompatibilityCheckResponse response = client(request -> {
            sent.set(request);
            return ok.exchange(request);
        }).checkCompatibility(userId, productId);

        assertThat(response.level()).isEqualTo(CompatibilityLevel.SEPARATE);
        assertThat(response.pairs()).hasSize(1);
        assertThat(response.pairs().get(0).ingredientA()).isEqualTo("레티놀");
        assertThat(response.pairs().get(0).schedule()).isEqualTo("레티놀은 저녁, AHA는 아침에 쓰세요");
        assertThat(sent.get().url().toString()).isEqualTo("http://ai/internal/compatibility/check");

        MockClientHttpRequest written = new MockClientHttpRequest(sent.get().method(), sent.get().url());
        sent.get().writeTo(written, ExchangeStrategies.withDefaults()).block();
        JsonNode body = new ObjectMapper().readTree(written.getBodyAsString().block());
        assertThat(body.get("userId").asText()).isEqualTo(userId.toString());
        assertThat(body.get("productId").asText()).isEqualTo(productId.toString());
    }

    @Test
    void 시간이_넘으면_기본값과_경고_로그를_남긴다(CapturedOutput output) {
        CompatibilityCheckResponse response = client(request -> Mono.never())
                .checkCompatibility(userId, productId, SHORT_TIMEOUT);

        assertDefault(response);
        assertThat(output).contains("WARN").contains("/internal/compatibility/check");
    }

    @Test
    void 오류_응답이면_기본값을_돌려준다(CapturedOutput output) {
        CompatibilityCheckResponse response = client(respond(HttpStatus.INTERNAL_SERVER_ERROR, "{}"))
                .checkCompatibility(userId, productId);

        assertDefault(response);
        assertThat(output).contains("WARN").contains("/internal/compatibility/check");
    }

    @Test
    void 연결에_실패하면_기본값을_돌려준다() {
        assertDefault(client(request -> Mono.error(new IllegalStateException("연결 실패")))
                .checkCompatibility(userId, productId));
    }

    @Test
    void 모르는_판정_단계면_기본값을_돌려준다() {
        assertDefault(client(respond(HttpStatus.OK, "{\"level\":\"DANGER\",\"pairs\":[],\"stub\":false}"))
                .checkCompatibility(userId, productId));
    }

    @Test
    void 판정_단계가_없거나_본문이_비면_기본값을_돌려준다() {
        assertDefault(client(respond(HttpStatus.OK, "{\"pairs\":[],\"stub\":false}"))
                .checkCompatibility(userId, productId));
        assertDefault(client(request -> Mono.just(ClientResponse.create(HttpStatus.OK).build()))
                .checkCompatibility(userId, productId));
    }

    @Test
    void 쌍_목록이_없으면_빈_목록으로_읽는다() {
        CompatibilityCheckResponse response = client(respond(HttpStatus.OK, "{\"level\":\"AVOID\",\"stub\":false}"))
                .checkCompatibility(userId, productId);

        assertThat(response.level()).isEqualTo(CompatibilityLevel.AVOID);
        assertThat(response.pairs()).isEmpty();
    }

    @Test
    void stub_응답이면_표시를_유지하고_경고_로그를_남긴다(CapturedOutput output) {
        CompatibilityCheckResponse response = client(respond(HttpStatus.OK, "{\"level\":\"OK\",\"pairs\":[],\"stub\":true}"))
                .checkCompatibility(userId, productId);

        assertThat(response.level()).isEqualTo(CompatibilityLevel.OK);
        assertThat(response.stub()).isTrue();
        assertThat(output).contains("WARN").contains("stub");
    }
}
