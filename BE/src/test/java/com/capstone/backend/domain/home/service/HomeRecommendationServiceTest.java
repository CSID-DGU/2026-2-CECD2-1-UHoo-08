package com.capstone.backend.domain.home.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.util.JsonUtil;
import com.capstone.backend.domain.home.dto.response.EnvironmentRecommendationResponse;
import com.capstone.backend.domain.home.dto.response.EnvironmentRecommendationResponse.CoveredCondition;
import com.capstone.backend.domain.home.dto.response.EnvironmentRecommendationResponse.MissingCondition;
import com.capstone.backend.domain.home.dto.response.RoutineCheckResponse;
import com.capstone.backend.domain.home.entity.HomeRecommendation;
import com.capstone.backend.domain.home.enums.HomeRecommendationKind;
import com.capstone.backend.domain.home.enums.HomeRecommendationState;
import com.capstone.backend.domain.home.repository.HomeRecommendationRepository;
import com.capstone.backend.domain.product.enums.UsageType;
import com.capstone.backend.domain.product.repository.ProductRepository;
import com.capstone.backend.domain.product.repository.UserProductRepository;
import com.capstone.backend.domain.recommendation.service.ResultAssembler;
import com.capstone.backend.domain.user.entity.User;
import com.capstone.backend.domain.user.repository.UserRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.beans.BeanUtils;
import org.springframework.test.util.ReflectionTestUtils;

import java.io.InputStream;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.tuple;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class HomeRecommendationServiceTest {

    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final OffsetDateTime GENERATED = OffsetDateTime.of(2026, 9, 20, 6, 10, 0, 0, ZoneOffset.UTC);
    private static final String CONDITIONS = """
            [{"key":"UV_PROTECT","label":"자외선 차단","basis":"6 이상 22일","covered":true,"coveredBy":"닥터지 선크림"},
             {"key":"SOOTHING","label":"진정","basis":"미세먼지 14일","covered":false,"coveredBy":null},
             {"key":"BARRIER","label":"보습막","basis":"습도 41%","covered":false}]""";

    @Mock
    UserRepository userRepository;
    @Mock
    HomeRecommendationRepository homeRecommendationRepository;
    @Mock
    ProductRepository productRepository;
    @Mock
    UserProductRepository userProductRepository;

    HomeRecommendationService service;

    private final UUID userId = UUID.randomUUID();
    private final UUID jobId = UUID.randomUUID();

    @BeforeEach
    void setUp() {
        service = new HomeRecommendationService(userRepository, homeRecommendationRepository, userProductRepository,
                new ResultAssembler(productRepository), new JsonUtil(MAPPER));
    }

    private void givenUser(String region) {
        given(userRepository.findById(userId)).willReturn(Optional.of(
                User.builder().id(userId).name("하림").provider("KAKAO").region(region).skinType("OILY").build()));
    }

    /** AI 가 쓰는 읽기 전용 엔티티라 생성자가 없다. 저장된 행을 읽어 온 것처럼 값을 채운다 */
    private void givenHomeEnv(String result) {
        HomeRecommendation row = BeanUtils.instantiateClass(HomeRecommendation.class);
        ReflectionTestUtils.setField(row, "userId", userId);
        ReflectionTestUtils.setField(row, "kind", HomeRecommendationKind.ENV);
        ReflectionTestUtils.setField(row, "jobId", jobId);
        ReflectionTestUtils.setField(row, "result", result);
        ReflectionTestUtils.setField(row, "generatedAt", GENERATED);
        given(homeRecommendationRepository.findById(new HomeRecommendation.Key(userId, HomeRecommendationKind.ENV)))
                .willReturn(Optional.of(row));
    }

    /** 홈 환경 결과 샘플에 조건 블록을 붙인다 */
    private static String sampleWithConditions() throws Exception {
        try (InputStream in = HomeRecommendationServiceTest.class.getResourceAsStream("/ai-results/HOME_ENV.json")) {
            ObjectNode result = (ObjectNode) MAPPER.readTree(in);
            result.set("conditions", MAPPER.readTree(CONDITIONS));
            return MAPPER.writeValueAsString(result);
        }
    }

    @Test
    void 권할_제품이_있으면_READY이고_조건을_부족한_것과_채운_것으로_나눈다() throws Exception {
        givenUser("경기");
        givenHomeEnv(sampleWithConditions());

        EnvironmentRecommendationResponse response = service.getEnvironment(userId);

        assertThat(response.getState()).isEqualTo(HomeRecommendationState.READY);
        assertThat(response.getMissingConditions()).extracting(MissingCondition::getKey, MissingCondition::getLabel)
                .containsExactly(tuple("SOOTHING", "진정"), tuple("BARRIER", "보습막"));
        assertThat(response.getCoveredConditions())
                .extracting(CoveredCondition::getKey, CoveredCondition::getLabel, CoveredCondition::getCoveredBy)
                .containsExactly(tuple("UV_PROTECT", "자외선 차단", "닥터지 선크림"));
        assertThat(response.getResult().getJobId()).isEqualTo(jobId);
        assertThat(response.getResult().getScenario()).isEqualTo("HOME_ENV");
        assertThat(response.getResult().getItems()).hasSize(1);
        assertThat(response.getResult().getItems().get(0).getBadges().get(0).getType()).isEqualTo("ENV");
        assertThat(response.getComputedAt()).isEqualTo(GENERATED);
    }

    @Test
    void 계산했지만_권할_제품이_없으면_FULLY_COVERED다() {
        givenUser("경기");
        givenHomeEnv("{\"scenario\":\"HOME_ENV\",\"items\":[],\"conditions\":"
                + "[{\"key\":\"UV_PROTECT\",\"label\":\"자외선 차단\",\"covered\":true,\"coveredBy\":\"닥터지 선크림\"}]}");

        EnvironmentRecommendationResponse response = service.getEnvironment(userId);

        assertThat(response.getState()).isEqualTo(HomeRecommendationState.FULLY_COVERED);
        assertThat(response.getMissingConditions()).isEmpty();
        assertThat(response.getCoveredConditions()).hasSize(1);
        assertThat(response.getResult().getItems()).isEmpty();
    }

    @Test
    void 결과가_없으면_NOT_READY이고_결과와_계산_시각은_null이다() {
        givenUser("경기");
        given(homeRecommendationRepository.findById(new HomeRecommendation.Key(userId, HomeRecommendationKind.ENV)))
                .willReturn(Optional.empty());

        EnvironmentRecommendationResponse response = service.getEnvironment(userId);

        assertThat(response.getState()).isEqualTo(HomeRecommendationState.NOT_READY);
        assertThat(response.getMissingConditions()).isEmpty();
        assertThat(response.getCoveredConditions()).isEmpty();
        assertThat(response.getResult()).isNull();
        assertThat(response.getComputedAt()).isNull();
    }

    @Test
    void 결과를_읽을_수_없으면_NOT_READY다() {
        givenUser("경기");
        givenHomeEnv("{깨진 json");

        assertThat(service.getEnvironment(userId).getState()).isEqualTo(HomeRecommendationState.NOT_READY);
    }

    @Test
    void 조건_블록이_없는_결과면_조건은_비어_있다() throws Exception {
        givenUser("경기");
        try (InputStream in = getClass().getResourceAsStream("/ai-results/HOME_ENV.json")) {
            givenHomeEnv(new String(in.readAllBytes()));
        }

        EnvironmentRecommendationResponse response = service.getEnvironment(userId);

        assertThat(response.getState()).isEqualTo(HomeRecommendationState.READY);
        assertThat(response.getMissingConditions()).isEmpty();
        assertThat(response.getCoveredConditions()).isEmpty();
    }

    @Test
    void 지역을_설정하지_않았으면_REGION_NOT_SET이다() {
        givenUser(null);

        assertThatThrownBy(() -> service.getEnvironment(userId))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.REGION_NOT_SET);
        verifyNoInteractions(homeRecommendationRepository);
    }

    // 루틴 점검

    private void givenHomeRoutine(String result) {
        HomeRecommendation row = BeanUtils.instantiateClass(HomeRecommendation.class);
        ReflectionTestUtils.setField(row, "userId", userId);
        ReflectionTestUtils.setField(row, "kind", HomeRecommendationKind.ROUTINE);
        ReflectionTestUtils.setField(row, "result", result);
        ReflectionTestUtils.setField(row, "generatedAt", GENERATED);
        given(homeRecommendationRepository.findById(new HomeRecommendation.Key(userId, HomeRecommendationKind.ROUTINE)))
                .willReturn(Optional.of(row));
    }

    @Test
    void 루틴_점검은_쓰는_중인_보유_제품을_세고_점검_결과를_꺼낸다() throws Exception {
        given(userProductRepository.countByUserIdAndUsageType(userId, UsageType.USING)).willReturn(5L);
        try (InputStream in = getClass().getResourceAsStream("/ai-results/HOME_ROUTINE.json")) {
            givenHomeRoutine(new String(in.readAllBytes()));
        }

        RoutineCheckResponse response = service.getRoutineCheck(userId);

        assertThat(response.isChecked()).isTrue();
        assertThat(response.getProductCount()).isEqualTo(5);
        assertThat(response.getPairs()).hasSize(3);
        assertThat(response.getReplacement()).isNotNull();
    }

    @Test
    void 루틴_점검_결과가_없거나_읽을_수_없으면_점검_전이다() {
        given(userProductRepository.countByUserIdAndUsageType(userId, UsageType.USING)).willReturn(2L);
        given(homeRecommendationRepository.findById(new HomeRecommendation.Key(userId, HomeRecommendationKind.ROUTINE)))
                .willReturn(Optional.empty());

        RoutineCheckResponse empty = service.getRoutineCheck(userId);

        assertThat(empty.isChecked()).isFalse();
        assertThat(empty.getProductCount()).isEqualTo(2);

        givenHomeRoutine("{깨진 json");
        assertThat(service.getRoutineCheck(userId).isChecked()).isFalse();
        verifyNoInteractions(userRepository);
    }
}
