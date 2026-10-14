package com.capstone.backend.domain.ingredient.entity;

import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.Immutable;

import java.time.OffsetDateTime;

/**
 * 성분 두 개의 조합 판정(ingredient_conflict_rules). 표준 성분명끼리 비교한다.
 *
 * AI 쪽이 관리하고 BE 는 읽기만 한다. 두 성분은 항상 사전 순(ingredientA < ingredientB)으로 들어 있다.
 */
@Entity
@Immutable
@Table(name = "ingredient_conflict_rules")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class IngredientConflictRule {

    @Id
    @Column(name = "id")
    private Long id;

    @Column(name = "ingredient_a", nullable = false, columnDefinition = "text")
    private String ingredientA;

    @Column(name = "ingredient_b", nullable = false, columnDefinition = "text")
    private String ingredientB;

    /** AVOID(함께 쓰지 않기) | SEPARATE(시간대 분리) */
    @Column(name = "level", nullable = false, length = 10)
    private String level;

    /** 화면에 그대로 나가는 문장 */
    @Column(name = "advice", nullable = false, columnDefinition = "text")
    private String advice;

    /** 규칙의 근거 */
    @Column(name = "source", nullable = false, columnDefinition = "text")
    private String source;

    @Column(name = "created_at", nullable = false)
    private OffsetDateTime createdAt;
}
