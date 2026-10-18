package com.capstone.backend.domain.product.service;

import com.capstone.backend.common.ai.AiInternalClient;
import com.capstone.backend.common.ai.dto.AiInternalDtos.ProductCandidate;
import com.capstone.backend.common.ai.dto.AiInternalDtos.RecognizePhotosRequest;
import com.capstone.backend.common.ai.dto.AiInternalDtos.RecognizePhotosResponse;
import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.common.storage.StorageService;
import com.capstone.backend.common.util.JsonUtil;
import com.capstone.backend.domain.product.dto.response.PhotoRecognitionResponse;
import com.capstone.backend.domain.product.dto.response.PhotoRecognitionResponse.Candidate;
import com.capstone.backend.domain.product.entity.PhotoRecognition;
import com.capstone.backend.domain.product.repository.PhotoRecognitionRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.OffsetDateTime;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.within;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.startsWith;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class PhotoRecognitionServiceTest {

    @Mock
    StorageService storageService;
    @Mock
    AiInternalClient aiInternalClient;
    @Mock
    PhotoRecognitionRepository photoRecognitionRepository;

    PhotoRecognitionService service;

    private final UUID userId = UUID.randomUUID();
    private final UUID recognitionId = UUID.randomUUID();
    private final MockMultipartFile image = new MockMultipartFile("image", "front.jpg", "image/jpeg", new byte[]{1});
    private final String imageUrl = "https://test.supabase.co/storage/v1/object/public/user-product-photos/a.jpg";

    @BeforeEach
    void setUp() {
        service = new PhotoRecognitionService(storageService, aiInternalClient, photoRecognitionRepository,
                new JsonUtil(new ObjectMapper()));
    }

    private void givenUploadAndSave() {
        given(storageService.upload(eq("user-product-photos"), startsWith(userId + "/"), eq(image)))
                .willReturn(imageUrl);
        given(photoRecognitionRepository.save(any(PhotoRecognition.class))).willAnswer(inv -> {
            PhotoRecognition saved = inv.getArgument(0);
            ReflectionTestUtils.setField(saved, "id", recognitionId);
            return saved;
        });
    }

    private static ProductCandidate candidate(String name, double confidence) {
        return new ProductCandidate(UUID.randomUUID().toString(), name, "이니스프리", "https://img/" + name, confidence);
    }

    @Test
    void 후보는_일치도_높은_순으로_3개까지_0에서_100_정수로_바꿔_돌려준다() {
        givenUploadAndSave();
        given(aiInternalClient.recognizePhotos(new RecognizePhotosRequest(imageUrl, null))).willReturn(
                new RecognizePhotosResponse(
                        List.of(candidate("C", 0.40), candidate("A", 0.955), candidate("D", 0.10), candidate("B", 0.71)),
                        null, null, null, Map.of("readText", "innisfree GREEN TEA SEED SERUM 80ml"), false));

        PhotoRecognitionResponse response = service.recognizeName(userId, image);

        assertThat(response.getRecognitionId()).isEqualTo(recognitionId);
        assertThat(response.getReadText()).isEqualTo("innisfree GREEN TEA SEED SERUM 80ml");
        assertThat(response.getCandidates()).extracting(Candidate::getName).containsExactly("A", "B", "C");
        assertThat(response.getCandidates()).extracting(Candidate::getMatchScore).containsExactly(96, 71, 40);
        assertThat(response.getCandidates()).extracting(Candidate::getVolume).containsOnlyNulls();
    }

    @Test
    void 인식_결과는_사진_주소와_후보_원본을_담아_30분_동안_보관한다() {
        givenUploadAndSave();
        Map<String, Object> raw = Map.of("text", "GREEN TEA");
        given(aiInternalClient.recognizePhotos(any())).willReturn(
                new RecognizePhotosResponse(List.of(candidate("A", 0.9)), null, null, null, raw, false));

        service.recognizeName(userId, image);

        ArgumentCaptor<PhotoRecognition> captor = ArgumentCaptor.forClass(PhotoRecognition.class);
        verify(photoRecognitionRepository).save(captor.capture());
        PhotoRecognition saved = captor.getValue();
        assertThat(saved.getUserId()).isEqualTo(userId);
        assertThat(saved.getNameImageUrl()).isEqualTo(imageUrl);
        assertThat(saved.getReadText()).isEqualTo("GREEN TEA");
        assertThat(saved.getCandidates()).contains("\"matchScore\":90");
        assertThat(saved.getRaw()).isEqualTo("{\"text\":\"GREEN TEA\"}");
        assertThat(saved.getExpiresAt()).isCloseTo(OffsetDateTime.now().plusMinutes(30), within(5, ChronoUnit.SECONDS));
    }

    @Test
    void 후보가_없어도_실패하지_않고_빈_목록과_빈_글자를_돌려준다() {
        givenUploadAndSave();
        given(aiInternalClient.recognizePhotos(any())).willReturn(
                new RecognizePhotosResponse(List.of(), null, null, null, Map.of(), false));

        PhotoRecognitionResponse response = service.recognizeName(userId, image);

        assertThat(response.getCandidates()).isEmpty();
        assertThat(response.getReadText()).isEmpty();
        verify(photoRecognitionRepository).save(any());
    }

    @Test
    void AI가_stub이면_후보를_쓰지_않고_빈_목록을_돌려준다() {
        givenUploadAndSave();
        given(aiInternalClient.recognizePhotos(any())).willReturn(
                new RecognizePhotosResponse(List.of(candidate("A", 0.9)), null, null, null, Map.of(), true));

        PhotoRecognitionResponse response = service.recognizeName(userId, image);

        assertThat(response.getCandidates()).isEmpty();
    }

    @Test
    void AI_호출이_실패하면_IMAGE_PARSE_FAILED이고_저장하지_않는다() {
        given(storageService.upload(any(), any(), any())).willReturn(imageUrl);
        given(aiInternalClient.recognizePhotos(any())).willThrow(new RuntimeException("timeout"));

        assertThatThrownBy(() -> service.recognizeName(userId, image))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.IMAGE_PARSE_FAILED);
        verify(photoRecognitionRepository, never()).save(any());
    }

    @Test
    void 용량을_넘으면_FILE_TOO_LARGE이고_AI를_부르지_않는다() {
        given(storageService.upload(any(), any(), any())).willThrow(new BusinessException(ErrorCode.FILE_TOO_LARGE));

        assertThatThrownBy(() -> service.recognizeName(userId, image))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.FILE_TOO_LARGE);
        verifyNoInteractions(aiInternalClient, photoRecognitionRepository);
    }

    @Test
    void 일치도는_0에서_100_사이_정수로_반올림한다() {
        assertThat(PhotoRecognitionService.toMatchScore(0.955)).isEqualTo(96);
        assertThat(PhotoRecognitionService.toMatchScore(0.0)).isZero();
        assertThat(PhotoRecognitionService.toMatchScore(1.0)).isEqualTo(100);
        assertThat(PhotoRecognitionService.toMatchScore(1.2)).isEqualTo(100);
        assertThat(PhotoRecognitionService.toMatchScore(-0.1)).isZero();
    }

    @Test
    void 읽은_글자는_원본에_문자열이_있을_때만_쓴다() {
        assertThat(PhotoRecognitionService.readTextOf(null)).isEmpty();
        assertThat(PhotoRecognitionService.readTextOf(Map.of("readText", 123))).isEmpty();
        assertThat(PhotoRecognitionService.readTextOf(Map.of("readText", "A", "text", "B"))).isEqualTo("A");
    }
}
