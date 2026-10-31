package com.capstone.backend.domain.home.service;

import com.capstone.backend.common.config.HwadamProperties;
import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.util.JsonUtil;
import com.capstone.backend.domain.home.dto.response.EnvironmentSummaryResponse;
import com.capstone.backend.domain.home.dto.response.EnvironmentSummaryResponse.Condition;
import com.capstone.backend.domain.home.entity.EnvDaily;
import com.capstone.backend.domain.home.entity.HomeRecommendation;
import com.capstone.backend.domain.home.enums.HomeRecommendationKind;
import com.capstone.backend.domain.home.repository.EnvDailyRepository;
import com.capstone.backend.domain.home.repository.HomeRecommendationRepository;
import com.capstone.backend.domain.user.entity.User;
import com.capstone.backend.domain.user.repository.UserRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.beans.BeanUtils;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.tuple;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class EnvironmentServiceTest {

    private static final LocalDate TODAY = LocalDate.of(2026, 9, 16);
    private static final LocalDate START = LocalDate.of(2026, 8, 20);
    private static final OffsetDateTime UPDATED = OffsetDateTime.of(2026, 9, 16, 6, 0, 0, 0, ZoneOffset.UTC);

    @Mock
    UserRepository userRepository;
    @Mock
    EnvDailyRepository envDailyRepository;
    @Mock
    HomeRecommendationRepository homeRecommendationRepository;

    EnvironmentService service;

    private final UUID userId = UUID.randomUUID();

    @BeforeEach
    void setUp() {
        service = new EnvironmentService(userRepository, envDailyRepository, homeRecommendationRepository,
                new HwadamProperties(), new JsonUtil(new ObjectMapper()));
    }

    private void givenUser(String region, String regionLabel) {
        given(userRepository.findById(userId)).willReturn(Optional.of(
                User.builder().id(userId).name("하림").provider("KAKAO").region(region).regionLabel(regionLabel).build()));
    }

    private void givenDays(List<EnvDaily> days) {
        given(envDailyRepository.findByRegionAndDateBetween("경기", START, TODAY)).willReturn(days);
    }

    private void givenNoHomeEnv() {
        given(homeRecommendationRepository.findById(new HomeRecommendation.Key(userId, HomeRecommendationKind.ENV)))
                .willReturn(Optional.empty());
    }

    /** AI 가 쓰는 읽기 전용 엔티티라 생성자가 없다. 저장된 행을 읽어 온 것처럼 값을 채운다 */
    private static EnvDaily day(LocalDate date, int sampleCount, Float humidity, Float uv, Float pm10, Float pm25) {
        EnvDaily day = BeanUtils.instantiateClass(EnvDaily.class);
        ReflectionTestUtils.setField(day, "region", "경기");
        ReflectionTestUtils.setField(day, "date", date);
        ReflectionTestUtils.setField(day, "sampleCount", sampleCount);
        ReflectionTestUtils.setField(day, "humidityAvg", humidity);
        ReflectionTestUtils.setField(day, "uvMax", uv);
        ReflectionTestUtils.setField(day, "pm10Avg", pm10);
        ReflectionTestUtils.setField(day, "pm25Avg", pm25);
        ReflectionTestUtils.setField(day, "updatedAt", UPDATED.minusDays(TODAY.toEpochDay() - date.toEpochDay()));
        return day;
    }

    @Test
    void 오늘을_포함한_28일을_세고_관측이_없는_날은_빼고_센다() {
        givenUser("경기", "고양시 덕양구");
        givenDays(List.of(
                day(TODAY, 24, 40f, 6f, 30f, 10f),               // 자외선 높음
                day(TODAY.minusDays(1), 24, 42f, 5.9f, 81f, 10f), // 미세먼지 나쁨(PM10)
                day(TODAY.minusDays(2), 24, 41f, 7f, 20f, 36f),   // 자외선 높음, 미세먼지 나쁨(PM2.5)
                day(TODAY.minusDays(3), 24, null, null, null, null),
                day(TODAY.minusDays(4), 0, 90f, 10f, 200f, 100f)  // 관측 없는 날은 세지 않는다
        ));
        givenNoHomeEnv();

        EnvironmentSummaryResponse response = service.getSummary(userId, TODAY);

        assertThat(response.getRegionName()).isEqualTo("고양시 덕양구");
        assertThat(response.getPeriodStart()).isEqualTo(START);
        assertThat(response.getPeriodEnd()).isEqualTo(TODAY);
        assertThat(response.getDayCount()).isEqualTo(4);
        assertThat(response.getStats().getUvHighDays()).isEqualTo(2);
        assertThat(response.getStats().getDustBadDays()).isEqualTo(2);
        assertThat(response.getStats().getAvgHumidity()).isEqualTo(41);
        assertThat(response.getUpdatedAt()).isEqualTo(UPDATED);
        assertThat(response.getConditions()).isEmpty();
        assertThat(response.getMissingCount()).isZero();
    }

    @Test
    void 최근_7일_습도가_3주_전_7일보다_15퍼센트포인트_이상_떨어지면_계절_전환이다() {
        givenUser("경기", "고양시 덕양구");
        List<EnvDaily> days = new ArrayList<>();
        for (int i = 0; i < 7; i++) {
            days.add(day(TODAY.minusDays(i), 24, 41f, null, null, null));
            days.add(day(START.plusDays(i), 24, 62f, null, null, null));
        }
        days.add(day(TODAY.minusDays(14), 24, 99f, null, null, null)); // 비교하는 두 주 밖의 날
        givenDays(days);
        givenNoHomeEnv();

        EnvironmentSummaryResponse response = service.getSummary(userId, TODAY);

        assertThat(response.getSeasonChange().getTitle()).isEqualTo("계절이 바뀌고 있어요");
        assertThat(response.getSeasonChange().getMessage()).isEqualTo("습도가 3주 만에 62% → 41%로 떨어졌어요");
    }

    @Test
    void 습도_차이가_기준보다_작거나_한쪽_주에_기록이_없으면_계절_전환이_없다() {
        givenUser("경기", null);
        givenDays(List.of(
                day(TODAY, 24, 50f, null, null, null),
                day(START, 24, 64f, null, null, null),
                day(START.plusDays(1), 0, 90f, null, null, null)));
        givenNoHomeEnv();

        EnvironmentSummaryResponse response = service.getSummary(userId, TODAY);

        assertThat(response.getSeasonChange()).isNull();
        assertThat(response.getRegionName()).isEqualTo("경기");
    }

    @Test
    void 습도가_오르면_올랐어요_문구다() {
        givenUser("경기", "고양시 덕양구");
        givenDays(List.of(day(TODAY, 24, 70f, null, null, null), day(START, 24, 50f, null, null, null)));
        givenNoHomeEnv();

        assertThat(service.getSummary(userId, TODAY).getSeasonChange().getMessage())
                .isEqualTo("습도가 3주 만에 50% → 70%로 올랐어요");
    }

    @Test
    void 기록이_하나도_없으면_빈_통계로_응답한다() {
        givenUser("경기", "고양시 덕양구");
        givenDays(List.of());
        givenNoHomeEnv();

        EnvironmentSummaryResponse response = service.getSummary(userId, TODAY);

        assertThat(response.getDayCount()).isZero();
        assertThat(response.getStats().getUvHighDays()).isZero();
        assertThat(response.getStats().getAvgHumidity()).isNull();
        assertThat(response.getSeasonChange()).isNull();
        assertThat(response.getUpdatedAt()).isNull();
    }

    @Test
    void 조건은_홈_환경_추천_결과에서_읽고_채우지_못한_조건을_센다() {
        givenUser("경기", "고양시 덕양구");
        givenDays(List.of());
        HomeRecommendation home = BeanUtils.instantiateClass(HomeRecommendation.class);
        ReflectionTestUtils.setField(home, "result", """
                {"conditions":[
                  {"key":"UV_PROTECT","label":"자외선 차단","basis":"6 이상 22일","covered":true,"coveredBy":"닥터지 선크림"},
                  {"key":"SOOTHING","label":"진정, 항산화","basis":"미세먼지 14일","covered":false,"coveredBy":null},
                  {"label":"키 없는 조건"},
                  {"key":"BARRIER","label":"보습막 형성","basis":"습도 41%","covered":false}
                ]}""");
        given(homeRecommendationRepository.findById(new HomeRecommendation.Key(userId, HomeRecommendationKind.ENV)))
                .willReturn(Optional.of(home));

        EnvironmentSummaryResponse response = service.getSummary(userId, TODAY);

        assertThat(response.getConditions())
                .extracting(Condition::getKey, Condition::isCovered, Condition::getCoveredBy)
                .containsExactly(
                        tuple("UV_PROTECT", true, "닥터지 선크림"),
                        tuple("SOOTHING", false, null),
                        tuple("BARRIER", false, null));
        assertThat(response.getMissingCount()).isEqualTo(2);
    }

    @Test
    void 지역을_설정하지_않았으면_REGION_NOT_SET이다() {
        givenUser(null, null);

        assertThatThrownBy(() -> service.getSummary(userId, TODAY))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.REGION_NOT_SET);
        verifyNoInteractions(envDailyRepository, homeRecommendationRepository);
    }
}
