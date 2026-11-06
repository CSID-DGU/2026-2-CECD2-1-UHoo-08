package com.capstone.backend.domain.recommendation.service;

import com.capstone.backend.domain.recommendation.dto.response.ClarifyFieldResponse;
import com.capstone.backend.domain.recommendation.enums.ClarifyInputType;
import org.assertj.core.groups.Tuple;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class ClarifyFieldMapperTest {

    @Test
    void 빠진_필드를_모르면_예산_세트는_예산과_구성을_묻는다() {
        List<ClarifyFieldResponse> fields = ClarifyFieldMapper.map("S6_BUNDLE", null);

        assertThat(fields).extracting(ClarifyFieldResponse::getKey).containsExactly("budget", "bundleSteps");
        ClarifyFieldResponse budget = fields.get(0);
        assertThat(budget.getLabel()).isEqualTo("예산은 얼마로 볼까요?");
        assertThat(budget.getInputType()).isEqualTo(ClarifyInputType.AMOUNT);
        assertThat(budget.getPresets()).containsExactly(30000, 50000, 100000);
        assertThat(fields.get(1).getInputType()).isEqualTo(ClarifyInputType.TEXT_LIST);
        assertThat(fields.get(1).getPresets()).isNull();
    }

    @Test
    void 빠진_필드를_모르면_그_외_시나리오는_문장_하나로_묻는다() {
        assertThat(ClarifyFieldMapper.map("S2_SEARCH", List.of()))
                .extracting(ClarifyFieldResponse::getKey, ClarifyFieldResponse::getInputType)
                .containsExactly(Tuple.tuple("category", ClarifyInputType.TEXT));
        assertThat(ClarifyFieldMapper.map(null, null)).extracting(ClarifyFieldResponse::getKey).containsExactly("category");
    }

    @Test
    void AI가_알려_준_빠진_필드는_그대로_항목으로_바꾼다() {
        List<ClarifyFieldResponse> fields = ClarifyFieldMapper.map("S2_SEARCH",
                List.of("base_product_ref", "budget.total", "category", "bundle_steps"));

        assertThat(fields).extracting(ClarifyFieldResponse::getKey)
                .containsExactly("baseProduct", "budget", "category", "bundleSteps");
        assertThat(fields.get(0).getInputType()).isEqualTo(ClarifyInputType.PRODUCT);
        assertThat(fields.get(0).getLabel()).isEqualTo("어떤 제품을 기준으로 볼까요?");
    }

    @Test
    void 모르는_필드는_건너뛰고_아는_것이_없으면_문장_하나로_묻는다() {
        assertThat(ClarifyFieldMapper.map("S6_BUNDLE", List.of("skin_type", "budget.total")))
                .extracting(ClarifyFieldResponse::getKey).containsExactly("budget");
        assertThat(ClarifyFieldMapper.map("S6_BUNDLE", List.of("skin_type")))
                .extracting(ClarifyFieldResponse::getKey).containsExactly("category");
    }

    @Test
    void 같은_필드가_여러_번_와도_한_번만_묻는다() {
        assertThat(ClarifyFieldMapper.map(null, List.of("budget.total", "budget.total")))
                .extracting(ClarifyFieldResponse::getKey).containsExactly("budget");
    }
}
