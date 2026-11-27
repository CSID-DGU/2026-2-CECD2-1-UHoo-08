package com.capstone.backend.domain.user.service;

import com.capstone.backend.domain.user.dto.request.RegionUpdateRequest;
import com.capstone.backend.domain.user.dto.response.OnboardingCompleteResponse;
import com.capstone.backend.domain.user.dto.response.ProfileUpdateResponse;
import com.capstone.backend.domain.user.dto.response.RegionResponse;
import com.capstone.backend.domain.user.dto.response.UserMeResponse;
import org.springframework.web.multipart.MultipartFile;

import java.util.UUID;

public interface UserService {
    UserMeResponse getMyInfo(UUID userId);
    ProfileUpdateResponse updateMyProfile(UUID userId, String name, String gender, MultipartFile image);
    OnboardingCompleteResponse completeOnboarding(UUID userId);
    RegionResponse updateRegion(UUID userId, RegionUpdateRequest request);
}
