package com.capstone.backend.domain.user.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.storage.StorageService;
import com.capstone.backend.domain.user.dto.request.RegionUpdateRequest;
import com.capstone.backend.domain.user.dto.response.ProfileUpdateResponse;
import com.capstone.backend.domain.user.dto.response.RegionResponse;
import com.capstone.backend.domain.user.entity.User;
import com.capstone.backend.domain.user.repository.UserRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.mock.web.MockMultipartFile;

import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class UserServiceImplTest {

    @Mock
    UserRepository userRepository;
    @Mock
    StorageService storageService;
    @InjectMocks
    UserServiceImpl userService;

    private final UUID userId = UUID.randomUUID();

    private void givenUser() {
        User user = User.builder().id(userId).name("하림").provider("KAKAO").build();
        given(userRepository.findById(userId)).willReturn(Optional.of(user));
        given(userRepository.save(any(User.class))).willAnswer(inv -> inv.getArgument(0));
    }

    @Test
    void 프로필_이미지는_profile_image_버킷의_사용자ID_경로로_올리고_URL을_저장한다() {
        givenUser();
        MockMultipartFile image = new MockMultipartFile("image", "me.png", "image/png", new byte[]{1});
        String url = "https://test.supabase.co/storage/v1/object/public/profile_image/" + userId + ".png";
        given(storageService.upload("profile_image", userId.toString(), image)).willReturn(url);

        ProfileUpdateResponse response = userService.updateMyProfile(userId, null, null, image);

        assertThat(response.getProfileImageUrl()).isEqualTo(url);
    }

    @Test
    void 프로필_이미지는_5MB를_넘으면_올리지_않고_FILE_TOO_LARGE다() {
        MockMultipartFile image = new MockMultipartFile("image", "me.png", "image/png",
                new byte[5 * 1024 * 1024 + 1]);

        assertThatThrownBy(() -> userService.updateMyProfile(userId, null, null, image))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.FILE_TOO_LARGE);
        verifyNoInteractions(storageService);
        verify(userRepository, never()).save(any());
    }

    @Test
    void 이미지_없이_이름만_바꾸면_업로드하지_않는다() {
        givenUser();

        ProfileUpdateResponse response = userService.updateMyProfile(userId, " 새이름 ", null, null);

        assertThat(response.getName()).isEqualTo("새이름");
        verify(storageService, never()).upload(any(), any(), any());
    }

    @Test
    void 업로드가_실패하면_프로필을_저장하지_않는다() {
        MockMultipartFile image = new MockMultipartFile("image", "me.gif", "image/gif", new byte[]{1});
        given(storageService.upload(eq("profile_image"), eq(userId.toString()), any()))
                .willThrow(new BusinessException(ErrorCode.VALIDATION_ERROR));

        assertThatThrownBy(() -> userService.updateMyProfile(userId, null, null, image))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.VALIDATION_ERROR);
        verify(userRepository, never()).save(any());
    }

    @Test
    void 지역은_시도_이름과_표시_이름을_함께_저장한다() {
        User user = User.builder().id(userId).name("하림").provider("KAKAO").build();
        given(userRepository.findById(userId)).willReturn(Optional.of(user));

        RegionResponse response = userService.updateRegion(userId, new RegionUpdateRequest(" 경기 ", " 고양시 덕양구 "));

        assertThat(user.getRegion()).isEqualTo("경기");
        assertThat(user.getRegionLabel()).isEqualTo("고양시 덕양구");
        assertThat(response.getRegionCode()).isEqualTo("경기");
        assertThat(response.getRegionName()).isEqualTo("고양시 덕양구");
    }

    @Test
    void 지원하지_않는_지역이면_저장하지_않고_VALIDATION_ERROR다() {
        for (String regionCode : new String[]{"41281", "광주", "전남", "Seoul"}) {
            assertThatThrownBy(() -> userService.updateRegion(userId, new RegionUpdateRequest(regionCode, "고양시 덕양구")))
                    .isInstanceOf(BusinessException.class)
                    .extracting("errorCode").isEqualTo(ErrorCode.VALIDATION_ERROR);
        }
        verifyNoInteractions(userRepository);
    }

    @Test
    void 광주와_전남은_전남광주로_저장한다() {
        User user = User.builder().id(userId).name("하림").provider("KAKAO").build();
        given(userRepository.findById(userId)).willReturn(Optional.of(user));

        userService.updateRegion(userId, new RegionUpdateRequest("전남광주", "광주 북구"));

        assertThat(user.getRegion()).isEqualTo("전남광주");
    }
}
