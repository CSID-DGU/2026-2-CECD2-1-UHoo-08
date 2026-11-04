package com.capstone.backend.domain.home.service;

import com.capstone.backend.common.util.JsonUtil;
import com.capstone.backend.domain.home.dto.response.EnvironmentSummaryResponse.Condition;
import com.capstone.backend.domain.home.dto.response.RoutineCheckResponse;
import com.capstone.backend.domain.home.entity.HomeRecommendation;
import com.capstone.backend.domain.home.enums.HomeRecommendationKind;
import com.capstone.backend.domain.home.repository.HomeRecommendationRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.BeanUtils;
import org.springframework.test.util.ReflectionTestUtils;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.tuple;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;

class HomeResultReaderTest {

    private static final OffsetDateTime GENERATED = OffsetDateTime.of(2026, 9, 20, 6, 10, 0, 0, ZoneOffset.UTC);

    private final HomeRecommendationRepository repository = mock(HomeRecommendationRepository.class);
    private final HomeResultReader reader = new HomeResultReader(repository, new JsonUtil(new ObjectMapper()));
    private final UUID userId = UUID.randomUUID();
    private final UUID jobId = UUID.randomUUID();

    private void givenRow(HomeRecommendationKind kind, String result) {
        HomeRecommendation row = BeanUtils.instantiateClass(HomeRecommendation.class);
        ReflectionTestUtils.setField(row, "jobId", jobId);
        ReflectionTestUtils.setField(row, "result", result);
        ReflectionTestUtils.setField(row, "generatedAt", GENERATED);
        given(repository.findById(new HomeRecommendation.Key(userId, kind))).willReturn(Optional.of(row));
    }

    private static String sample(String name) throws IOException {
        try (InputStream in = HomeResultReaderTest.class.getResourceAsStream("/ai-results/" + name)) {
            return new String(in.readAllBytes(), StandardCharsets.UTF_8);
        }
    }

    @Test
    void 행을_읽어_실행과_시각과_결과를_돌려준다() throws IOException {
        givenRow(HomeRecommendationKind.ENV, sample("HOME_ENV.json"));

        HomeResultReader.Card card = reader.find(userId, HomeRecommendationKind.ENV).orElseThrow();

        assertThat(card.jobId()).isEqualTo(jobId);
        assertThat(card.generatedAt()).isEqualTo(GENERATED);
        assertThat(card.result().path("scenario").asText()).isEqualTo("HOME_ENV");
    }

    @Test
    void 환경_샘플의_조건_블록을_읽는다() throws IOException {
        givenRow(HomeRecommendationKind.ENV, sample("HOME_ENV.json"));

        assertThat(HomeResultReader.conditionsOf(reader.find(userId, HomeRecommendationKind.ENV).orElseThrow()).orElseThrow())
                .extracting(Condition::getKey, Condition::isCovered, Condition::getCoveredBy)
                .containsExactly(tuple("UV_PROTECT", true, "닥터지 선크림"), tuple("SOOTHING", false, null));
    }

    @Test
    void 루틴_샘플의_점검_블록을_읽는다() throws IOException {
        givenRow(HomeRecommendationKind.ROUTINE, sample("HOME_ROUTINE.json"));
        Set<UUID> using = Set.of(
                UUID.fromString("aaaaaaaa-0000-0000-0000-000000000001"), UUID.fromString("aaaaaaaa-0000-0000-0000-000000000002"),
                UUID.fromString("aaaaaaaa-0000-0000-0000-000000000003"), UUID.fromString("aaaaaaaa-0000-0000-0000-000000000004"),
                UUID.fromString("aaaaaaaa-0000-0000-0000-000000000005"));

        RoutineCheckResponse response = RoutineCheckBuilder.build(
                reader.find(userId, HomeRecommendationKind.ROUTINE).orElseThrow().result(), using);

        assertThat(response.getCounts().getAvoid()).isEqualTo(1);
        assertThat(response.getPairs()).hasSize(3);
        assertThat(response.getReplacement()).isNotNull();
        assertThat(response.getUncomparedCount()).isEqualTo(1);
    }

    @Test
    void 행이_없으면_비어_있다() {
        given(repository.findById(new HomeRecommendation.Key(userId, HomeRecommendationKind.ENV))).willReturn(Optional.empty());

        assertThat(reader.find(userId, HomeRecommendationKind.ENV)).isEmpty();
    }

    @Test
    void 읽을_수_없는_결과나_객체가_아닌_결과는_비어_있다() {
        givenRow(HomeRecommendationKind.ROUTINE, "{broken");
        assertThat(reader.find(userId, HomeRecommendationKind.ROUTINE)).isEmpty();

        givenRow(HomeRecommendationKind.ROUTINE, "[]");
        assertThat(reader.find(userId, HomeRecommendationKind.ROUTINE)).isEmpty();
    }

    @Test
    void 조건_블록이_없는_옛_결과는_분석_전이고_key가_없는_항목은_건너뛴다() {
        givenRow(HomeRecommendationKind.ENV, "{\"scenario\":\"HOME_ENV\"}");
        assertThat(HomeResultReader.conditionsOf(reader.find(userId, HomeRecommendationKind.ENV).orElseThrow())).isEmpty();

        givenRow(HomeRecommendationKind.ENV, "{\"conditions\":[{\"label\":\"x\"},{\"key\":\"SOOTHING\"}]}");
        assertThat(HomeResultReader.conditionsOf(reader.find(userId, HomeRecommendationKind.ENV).orElseThrow()).orElseThrow())
                .extracting(Condition::getKey, Condition::getLabel).containsExactly(tuple("SOOTHING", "SOOTHING"));
    }
}
