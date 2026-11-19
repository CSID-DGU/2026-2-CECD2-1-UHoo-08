package com.capstone.backend.domain.product.service;

import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import static org.assertj.core.api.Assertions.assertThat;

class ProductTextSearchServiceTest {

    @ParameterizedTest
    @CsvSource({
            "롬앤 베러 댄 아이섀도우 팔레트, eye",
            "클리오 킬 브로우 펜슬, eye",
            "메이블린 래쉬 마스카라, eye",
            "투쿨포스쿨 아트클래스 바이 로댕 쉐딩, cheek",
            "페리페라 퓨어 블러쉬드 선샤인 치크, cheek",
            "에뛰드 하이라이터 스틱, cheek",
            "라네즈 네오 쿠션, base",
            "웨이크메이크 립라이너, lip",
            "AHC 아이크림 포 페이스, skincare",
            "라운드랩 독도 토너, skincare",
    })
    void 상품_이름으로_카테고리를_나누고_아이와_치크도_나눈다(String name, String expected) {
        assertThat(ProductTextSearchService.mapCategory("화장품/미용", name)).isEqualTo(expected);
    }
}
