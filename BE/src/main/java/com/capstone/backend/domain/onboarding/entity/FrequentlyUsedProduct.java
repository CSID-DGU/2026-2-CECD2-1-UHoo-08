package com.capstone.backend.domain.onboarding.entity;

import com.capstone.backend.domain.product.entity.Product;
import com.capstone.backend.domain.user.entity.User;
import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDateTime;
import java.util.UUID;

/**
 * 온보딩에서 고른 자주 사용하는 제품. 지금 쓰는 중인지와 상관없는 취향 정보라 보유 제품(user_products)과 따로 둔다.
 * 사용자와 제품마다 한 줄이다.
 */
@Entity
@Table(name = "frequently_used_products")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder
public class FrequentlyUsedProduct {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id")
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", nullable = false)
    private User user;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "product_id", nullable = false)
    private Product product;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;
}
