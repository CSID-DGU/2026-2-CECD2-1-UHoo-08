package com.capstone.backend.domain.user.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.storage.StorageService;
import com.capstone.backend.domain.pricetracking.repository.PriceTrackingRepository;
import com.capstone.backend.domain.onboarding.repository.RegisteredRepository;
import com.capstone.backend.domain.user.dto.response.OnboardingCompleteResponse;
import com.capstone.backend.domain.user.dto.response.ProfileUpdateResponse;
import com.capstone.backend.domain.user.dto.response.UserMeResponse;
import com.capstone.backend.domain.user.entity.User;
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
    private final RegisteredRepository registeredRepository;
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
        long registeredCount = registeredRepository.countByUserId(userId);

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

}
