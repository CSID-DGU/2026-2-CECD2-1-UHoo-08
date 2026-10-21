package com.capstone.backend.domain.recommendation.service;

import com.capstone.backend.common.ai.AiInternalClient;
import com.capstone.backend.common.ai.dto.AiInternalDtos.AgentRunV2Request;
import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.util.JsonUtil;
import com.capstone.backend.domain.recommendation.dto.request.RecommendationQueryRequest;
import com.capstone.backend.domain.recommendation.dto.request.RecommendationQueryRequest.TargetProfile;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationQueryResponse;
import com.capstone.backend.domain.recommendation.entity.Recommendation;
import com.capstone.backend.domain.recommendation.entity.SearchLog;
import com.capstone.backend.domain.recommendation.enums.JobStatus;
import com.capstone.backend.domain.recommendation.enums.RecommendationBasis;
import com.capstone.backend.domain.recommendation.enums.TargetRelation;
import com.capstone.backend.domain.recommendation.enums.TargetSkinConcern;
import com.capstone.backend.domain.recommendation.enums.TargetSkinType;
import com.capstone.backend.domain.recommendation.repository.RecommendationRepository;
import com.capstone.backend.domain.recommendation.repository.SearchLogRepository;
import com.capstone.backend.domain.user.entity.User;
import com.capstone.backend.domain.user.repository.UserRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.willThrow;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class RecommendationJobServiceTest {

    @Mock
    RecommendationRepository recommendationRepository;
    @Mock
    SearchLogRepository searchLogRepository;
    @Mock
    UserRepository userRepository;
    @Mock
    AiInternalClient aiInternalClient;

    RecommendationJobService service;

    private final UUID userId = UUID.randomUUID();
    private final UUID jobId = UUID.randomUUID();

    @BeforeEach
    void setUp() {
        service = new RecommendationJobService(recommendationRepository, searchLogRepository, userRepository,
                aiInternalClient, new JsonUtil(new ObjectMapper()));
    }

    @AfterEach
    void tearDown() {
        if (TransactionSynchronizationManager.isSynchronizationActive()) {
            TransactionSynchronizationManager.clearSynchronization();
        }
    }

    private void givenUser(String skinType) {
        User user = User.builder().id(userId).name("하림").provider("KAKAO").skinType(skinType).build();
        given(userRepository.findById(userId)).willReturn(Optional.of(user));
    }

    private ArgumentCaptor<Recommendation> givenSave() {
        ArgumentCaptor<Recommendation> captor = ArgumentCaptor.forClass(Recommendation.class);
        given(recommendationRepository.save(captor.capture())).willAnswer(inv -> {
            Recommendation job = inv.getArgument(0);
            ReflectionTestUtils.setField(job, "id", jobId);
            return job;
        });
        return captor;
    }

    @Test
    void 대기_상태의_job과_검색_기록을_만들고_AI_추천_실행을_부른다() {
        givenUser("DRY");
        ArgumentCaptor<Recommendation> saved = givenSave();

        RecommendationQueryResponse response = service.requestQuery(userId,
                RecommendationQueryRequest.builder().query("  여름 가벼운 매트 쿠션 ").build());

        assertThat(response.getJobId()).isEqualTo(jobId);
        assertThat(response.getEstimatedSeconds()).isEqualTo(8);
        assertThat(response.getStatusUrl()).isEqualTo("/recommendations/" + jobId + "/status");

        Recommendation job = saved.getValue();
        assertThat(job.getStatus()).isEqualTo(JobStatus.PENDING);
        assertThat(job.getProgress()).isZero();
        assertThat(job.getRawQuery()).isEqualTo("여름 가벼운 매트 쿠션");
        assertThat(job.getBasis()).isEqualTo(RecommendationBasis.SELF);
        assertThat(job.getTargetProfile()).isNull();

        ArgumentCaptor<SearchLog> log = ArgumentCaptor.forClass(SearchLog.class);
        verify(searchLogRepository).save(log.capture());
        assertThat(log.getValue().getUserId()).isEqualTo(userId);
        assertThat(log.getValue().getJobId()).isEqualTo(jobId);
        assertThat(log.getValue().getRawQuery()).isEqualTo("여름 가벼운 매트 쿠션");
        assertThat(log.getValue().isClarified()).isFalse();

        verify(aiInternalClient).runAgentV2(new AgentRunV2Request(jobId.toString(), userId.toString(),
                "여름 가벼운 매트 쿠션", "SELF", null, null));
    }

    @Test
    void 다른_사람_기준이면_쓰실_분_정보를_저장하고_AI에_넘긴다() {
        givenUser(null);
        ArgumentCaptor<Recommendation> saved = givenSave();
        TargetProfile profile = TargetProfile.builder().relation(TargetRelation.MOM).skinType(TargetSkinType.DRY)
                .skinConcerns(List.of(TargetSkinConcern.SENSITIVE)).build();

        service.requestQuery(userId, RecommendationQueryRequest.builder()
                .query("엄마 선물").basis(RecommendationBasis.OTHER).targetProfile(profile).build());

        assertThat(saved.getValue().getBasis()).isEqualTo(RecommendationBasis.OTHER);
        assertThat(saved.getValue().getTargetProfile())
                .isEqualTo("{\"relation\":\"MOM\",\"personalColor\":null,\"skinType\":\"DRY\",\"skinConcerns\":[\"SENSITIVE\"]}");
        ArgumentCaptor<AgentRunV2Request> ai = ArgumentCaptor.forClass(AgentRunV2Request.class);
        verify(aiInternalClient).runAgentV2(ai.capture());
        assertThat(ai.getValue().basis()).isEqualTo("OTHER");
        assertThat(ai.getValue().targetProfile()).containsEntry("relation", "MOM")
                .containsEntry("skinConcerns", List.of("SENSITIVE"));
    }

    @Test
    void 다른_사람_기준이_아니면_쓰실_분_정보는_버린다() {
        givenUser("DRY");
        ArgumentCaptor<Recommendation> saved = givenSave();

        service.requestQuery(userId, RecommendationQueryRequest.builder().query("쿠션").basis(RecommendationBasis.POPULAR)
                .targetProfile(TargetProfile.builder().relation(TargetRelation.MOM).build()).build());

        assertThat(saved.getValue().getTargetProfile()).isNull();
    }

    @Test
    void 인기_기준은_피부_정보가_없어도_된다() {
        givenUser(null);
        givenSave();

        service.requestQuery(userId, RecommendationQueryRequest.builder().query("쿠션").basis(RecommendationBasis.POPULAR).build());

        verify(aiInternalClient).runAgentV2(any());
    }

    @Test
    void 내_피부_기준인데_피부_정보가_없으면_SKIN_PROFILE_NOT_FOUND이고_job을_만들지_않는다() {
        givenUser(" ");

        assertThatThrownBy(() -> service.requestQuery(userId, RecommendationQueryRequest.builder().query("쿠션").build()))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.SKIN_PROFILE_NOT_FOUND);
        verify(recommendationRepository, never()).save(any());
        verifyNoInteractions(aiInternalClient, searchLogRepository);
    }

    @Test
    void AI_호출이_실패해도_접수_결과를_돌려준다() {
        givenUser("DRY");
        givenSave();
        willThrow(new RuntimeException("connection refused")).given(aiInternalClient).runAgentV2(any());

        RecommendationQueryResponse response = service.requestQuery(userId,
                RecommendationQueryRequest.builder().query("쿠션").build());

        assertThat(response.getJobId()).isEqualTo(jobId);
    }

    @Test
    void 트랜잭션_안에서는_커밋된_뒤에_AI를_부른다() {
        givenUser("DRY");
        givenSave();
        TransactionSynchronizationManager.initSynchronization();

        service.requestQuery(userId, RecommendationQueryRequest.builder().query("쿠션").build());

        verifyNoInteractions(aiInternalClient);
        List<TransactionSynchronization> synchronizations = TransactionSynchronizationManager.getSynchronizations();
        synchronizations.forEach(TransactionSynchronization::afterCommit);
        verify(aiInternalClient).runAgentV2(any());
    }
}
