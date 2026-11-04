package com.capstone.backend.common.ai;

import com.capstone.backend.common.ai.dto.AiInternalDtos.Accepted;
import com.capstone.backend.common.ai.dto.AiInternalDtos.AgentClarifyRequest;
import com.capstone.backend.common.ai.dto.AiInternalDtos.AgentRunV2Request;
import com.capstone.backend.common.ai.dto.AiInternalDtos.BundleSwapRequest;
import com.capstone.backend.common.ai.dto.AiInternalDtos.BundleSwapResponse;
import com.capstone.backend.common.ai.dto.AiInternalDtos.CompatibilityCheckRequest;
import com.capstone.backend.common.ai.dto.AiInternalDtos.CompatibilityCheckResponse;
import com.capstone.backend.common.ai.dto.AiInternalDtos.FeedbackApplyRequest;
import com.capstone.backend.common.ai.dto.AiInternalDtos.HomeRunRequest;
import com.capstone.backend.common.ai.dto.AiInternalDtos.RecognizePhotosRequest;
import com.capstone.backend.common.ai.dto.AiInternalDtos.RecognizePhotosResponse;
import com.capstone.backend.common.ai.dto.AiInternalDtos.TrendsResponse;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import java.util.stream.Collectors;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * BE DTO 가 docs/internal-api-fixtures 의 예시 JSON 과 같은 모양인지 확인한다.
 *
 * AI 스키마는 모르는 필드를 422 로 거부하고, BE DTO 는 필드 이름이 하나 틀려도 컴파일된다.
 * 예시를 DTO 로 읽어 다시 JSON 으로 쓴 결과가 예시와 같아야 한다. 모르는 필드는 오류로 처리하므로
 * 예시에만 있는 필드와 DTO 에만 있는 필드가 모두 드러난다.
 * 계약이 바뀌면 예시를 먼저 고치고 DTO 를 고친다. 같은 예시를 AI 쪽에서도 검사하면 한쪽만 바꿨을 때 테스트가 깨진다.
 */
class AiContractTest {

    /** gradle 테스트는 BE 폴더에서 돈다 */
    private static final Path FIXTURES = Path.of("..", "docs", "internal-api-fixtures");

    private static final ObjectMapper MAPPER = new ObjectMapper()
            .enable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES);

    private static final Map<String, Class<?>> CONTRACTS = Map.ofEntries(
            Map.entry("accepted.response", Accepted.class),
            Map.entry("agent-run-v2.request", AgentRunV2Request.class),
            Map.entry("agent-clarify.request", AgentClarifyRequest.class),
            Map.entry("recognize-photos.request", RecognizePhotosRequest.class),
            Map.entry("recognize-photos.response", RecognizePhotosResponse.class),
            Map.entry("home-run.request", HomeRunRequest.class),
            Map.entry("bundle-swap.request", BundleSwapRequest.class),
            Map.entry("bundle-swap.response", BundleSwapResponse.class),
            Map.entry("trends.response", TrendsResponse.class),
            Map.entry("feedback-apply.request", FeedbackApplyRequest.class),
            Map.entry("compatibility-check.request", CompatibilityCheckRequest.class),
            Map.entry("compatibility-check.response", CompatibilityCheckResponse.class)
    );

    static Stream<Arguments> contracts() {
        return CONTRACTS.entrySet().stream().map(entry -> Arguments.of(entry.getKey(), entry.getValue()));
    }

    @ParameterizedTest(name = "{0}")
    @MethodSource("contracts")
    void DTO는_예시_JSON과_필드가_같다(String fixture, Class<?> dtoType) throws IOException {
        JsonNode expected = MAPPER.readTree(FIXTURES.resolve(fixture + ".json").toFile());

        Object dto = MAPPER.treeToValue(expected, dtoType);

        JsonNode actual = MAPPER.valueToTree(dto);
        assertThat(actual).isEqualTo(expected);
    }

    @Test
    void 사진_인식_요청은_없는_면을_보내지_않는다() {
        JsonNode dateOnly = MAPPER.valueToTree(new RecognizePhotosRequest(null, "https://x/date.jpg"));
        JsonNode nameOnly = MAPPER.valueToTree(new RecognizePhotosRequest("https://x/name.jpg", null));

        assertThat(dateOnly.has("nameImage")).isFalse();
        assertThat(dateOnly.get("dateImage").asText()).isEqualTo("https://x/date.jpg");
        assertThat(nameOnly.has("dateImage")).isFalse();
        assertThat(nameOnly.get("nameImage").asText()).isEqualTo("https://x/name.jpg");
    }

    @Test
    void 예시_JSON은_모두_DTO와_짝이_있다() throws IOException {
        try (Stream<Path> files = Files.list(FIXTURES)) {
            assertThat(files.map(path -> path.getFileName().toString().replaceFirst("\\.json$", ""))
                    .collect(Collectors.toSet())).isEqualTo(CONTRACTS.keySet());
        }
    }
}
