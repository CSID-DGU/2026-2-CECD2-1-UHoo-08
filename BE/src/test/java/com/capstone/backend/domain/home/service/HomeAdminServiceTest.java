package com.capstone.backend.domain.home.service;

import com.capstone.backend.common.ai.AiInternalClient;
import com.capstone.backend.common.ai.dto.AiInternalDtos.HomeRunRequest;
import com.capstone.backend.common.config.HwadamProperties;
import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.domain.home.enums.HomeRecommendationKind;
import com.capstone.backend.domain.user.repository.UserRepository;
import org.junit.jupiter.api.Test;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;

import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

class HomeAdminServiceTest {

    private final UserRepository userRepository = mock(UserRepository.class);
    private final AiInternalClient aiInternalClient = mock(AiInternalClient.class);
    private final HwadamProperties properties = new HwadamProperties();
    private final HomeAdminService service = new HomeAdminService(properties, userRepository, aiInternalClient);

    private final UUID adminId = UUID.randomUUID();
    private final UUID userId = UUID.randomUUID();

    @Test
    void 관리자가_있는_사용자를_요청하면_AI를_부른다() {
        properties.getAdmin().setUserIds(List.of(adminId));
        given(userRepository.existsById(userId)).willReturn(true);

        service.requestCard(adminId, userId, HomeRecommendationKind.ENV);

        verify(aiInternalClient).runHome(new HomeRunRequest(userId.toString(), "ENV"));
    }

    @Test
    void 관리자가_아니면_FORBIDDEN이고_사용자를_찾지_않는다() {
        properties.getAdmin().setUserIds(List.of(adminId));

        assertThatThrownBy(() -> service.requestCard(userId, userId, HomeRecommendationKind.ROUTINE))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.FORBIDDEN);
        verifyNoInteractions(userRepository, aiInternalClient);
    }

    @Test
    void 관리자_목록이_비어_있으면_아무도_부를_수_없다() {
        assertThatThrownBy(() -> service.requestCard(adminId, userId, HomeRecommendationKind.ROUTINE))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.FORBIDDEN);
        verifyNoInteractions(aiInternalClient);
    }

    @Test
    void 없는_사용자면_NOT_FOUND이고_AI를_부르지_않는다() {
        properties.getAdmin().setUserIds(List.of(adminId));
        given(userRepository.existsById(userId)).willReturn(false);

        assertThatThrownBy(() -> service.requestCard(adminId, userId, HomeRecommendationKind.ROUTINE))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.NOT_FOUND);
        verifyNoInteractions(aiInternalClient);
    }

    @EnableConfigurationProperties(HwadamProperties.class)
    static class PropertiesConfig {
    }

    private final ApplicationContextRunner runner = new ApplicationContextRunner().withUserConfiguration(PropertiesConfig.class);

    @Test
    void 관리자_설정은_쉼표로_구분한_ID이고_비어_있어도_뜬다() {
        runner.withPropertyValues("hwadam.admin.user-ids=" + adminId + "," + userId).run(context ->
                assertThat(context.getBean(HwadamProperties.class).getAdmin().getUserIds())
                        .containsExactly(adminId, userId));
        runner.withPropertyValues("hwadam.admin.user-ids=").run(context ->
                assertThat(context.getBean(HwadamProperties.class).getAdmin().getUserIds()).isEmpty());
    }
}
