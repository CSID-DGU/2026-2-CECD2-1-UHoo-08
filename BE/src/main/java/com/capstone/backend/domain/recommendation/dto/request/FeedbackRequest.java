package com.capstone.backend.domain.recommendation.dto.request;

import com.capstone.backend.domain.recommendation.enums.FeedbackReason;
import com.capstone.backend.domain.recommendation.enums.FeedbackVote;
import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.util.List;
import java.util.UUID;

/** 추천 결과의 제품 하나에 대한 반응. 이유는 별로예요일 때만 쓴다. 목록에 없는 반응이나 이유는 요청 오류다 */
@Getter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class FeedbackRequest {

    @NotNull(message = "productId는 필수입니다.")
    private UUID productId;

    @NotNull(message = "vote는 필수입니다.")
    private FeedbackVote vote;

    private List<FeedbackReason> reasonTags;
}
