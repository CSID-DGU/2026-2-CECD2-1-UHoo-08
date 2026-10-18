package com.capstone.backend.domain.product.controller;

import com.capstone.backend.common.response.ApiResponse;
import com.capstone.backend.domain.product.dto.response.PhotoRecognitionResponse;
import com.capstone.backend.domain.product.service.PhotoRecognitionService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.util.UUID;

@RestController
@RequiredArgsConstructor
@Tag(name = "10. User Products", description = "보유 제품 API")
public class UserProductController {

    private final PhotoRecognitionService photoRecognitionService;

    @Operation(
            summary = "제품명 사진 인식",
            description = "제품 앞면 사진에서 글자를 읽고 상품 후보를 일치도순으로 최대 3개 돌려준다. 후보가 없어도 200. " +
                    "recognitionId 는 30분 동안 유효하며 기한 사진 인식·보유 제품 등록에 쓴다. " +
                    "jpg/png/heic/webp, 최대 10MB."
    )
    @PostMapping(value = "/user-products/recognitions", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<ApiResponse<PhotoRecognitionResponse>> recognizeName(
            @AuthenticationPrincipal UUID userId,
            // 파일이 없을 때 스프링 기본 오류(500) 대신 업로드 검사의 VALIDATION_ERROR 로 응답하도록 필수로 두지 않는다
            @RequestPart(value = "image", required = false) MultipartFile image) {
        return ResponseEntity.ok(ApiResponse.success(photoRecognitionService.recognizeName(userId, image)));
    }
}
