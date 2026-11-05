package com.capstone.backend.domain.user.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.storage.StorageService;
import com.capstone.backend.domain.pricetracking.repository.PriceTrackingRepository;
import com.capstone.backend.domain.product.enums.UsageType;
import com.capstone.backend.domain.product.repository.UserProductRepository;
import com.capstone.backend.domain.user.dto.request.RegionUpdateRequest;
import com.capstone.backend.domain.user.dto.response.OnboardingCompleteResponse;
import com.capstone.backend.domain.user.dto.response.ProfileUpdateResponse;
import com.capstone.backend.domain.user.dto.response.RegionResponse;
import com.capstone.backend.domain.user.dto.response.UserMeResponse;
import com.capstone.backend.domain.user.entity.User;
import com.capstone.backend.domain.user.enums.SupportedRegion;
import com.capstone.backend.domain.user.repository.UserRepository;
import com.capstone.backend.domain.wishlist.repository.WishlistRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.util.UUID;

@Slf4j
@Service
@RequiredArgsConstructor
public class UserServiceImpl implements UserService {

    private final UserRepository userRepository;
    private final WishlistRepository wishlistRepository;
    private final PriceTrackingRepository priceTrackingRepository;
    private final UserProductRepository userProductRepository;
    private final StorageService storageService;

    private static final String PROFILE_IMAGE_BUCKET = "profile_image";
    private static final long PROFILE_IMAGE_MAX_SIZE = 5L * 1024 * 1024;

    @Override
    @Transactional(readOnly = true)
    public UserMeResponse getMyInfo(UUID userId) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));

        long wishlistCount = wishlistRepository.countByUserId(userId);
        long trackingCount = priceTrackingRepository.countByUserId(userId);
        // 마이페이지의 "구매 제품" 칸이다. 온보딩의 자주 사용하는 제품이 아니라 쓰는 중인 보유 제품을 센다
        long registeredCount = userProductRepository.countByUserIdAndUsageType(userId, UsageType.USING);

        return UserMeResponse.of(user, wishlistCount, trackingCount, registeredCount);
    }

    @Override
    public ProfileUpdateResponse updateMyProfile(UUID userId, String name, String gender, MultipartFile image) {
        String trimmedName = (name != null && !name.isBlank()) ? name.trim() : null;
        if (trimmedName != null && (trimmedName.length() < 2 || trimmedName.length() > 20)) {
            throw new BusinessException(ErrorCode.VALIDATION_ERROR);
        }
        if (image != null && !image.isEmpty() && image.getSize() > PROFILE_IMAGE_MAX_SIZE) {
            throw new BusinessException(ErrorCode.FILE_TOO_LARGE);
        }

        String profileImageUrl = null;
        if (image != null && !image.isEmpty()) {
            profileImageUrl = storageService.upload(PROFILE_IMAGE_BUCKET, userId.toString(), image);
        }

        return saveProfile(userId, trimmedName, gender, profileImageUrl);
    }

    @Transactional
    protected ProfileUpdateResponse saveProfile(UUID userId, String name, String gender, String profileImageUrl) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));
        user.updateProfile(name != null ? name.trim() : null, gender, profileImageUrl);
        return ProfileUpdateResponse.from(userRepository.save(user));
    }

    @Override
    @Transactional
    public OnboardingCompleteResponse completeOnboarding(UUID userId) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));
        user.completeOnboarding();
        User saved = userRepository.save(user);
        return new OnboardingCompleteResponse(true, saved.getUpdatedAt());
    }

    /** 환경 데이터가 시·도 단위라 지원 지역의 시·도 이름만 받는다. 지원하지 않는 지역이면 VALIDATION_ERROR */
    @Override
    @Transactional
    public RegionResponse updateRegion(UUID userId, RegionUpdateRequest request) {
        SupportedRegion region = SupportedRegion.fromName(request.getRegionCode().strip())
                .orElseThrow(() -> new BusinessException(ErrorCode.VALIDATION_ERROR));
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));
        user.updateRegion(region.regionName(), request.getRegionName().strip());
        return RegionResponse.from(user);
    }
}
