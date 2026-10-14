package com.capstone.backend.common.util;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.MissingNode;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

/**
 * jsonb 컬럼 문자열(recommendation_jobs.result, state_snapshot, steps 등)을 읽고 쓰는 헬퍼.
 *
 * Spring 의 ObjectMapper 빈을 써서 응답 직렬화와 같은 Jackson 설정을 따른다.
 * 깨진 JSON 은 저장된 데이터의 문제라 INTERNAL_ERROR 로 던진다. 화면을 살려야 하는 곳은 호출하는 쪽에서 잡는다.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class JsonUtil {

    private final ObjectMapper objectMapper;

    /**
     * jsonb 문자열을 트리로 읽는다. null·빈 문자열은 MissingNode 를 돌려줘서 {@code path("a").path("b")} 를 그대로 이어 쓸 수 있다.
     */
    public JsonNode readTree(String json) {
        if (json == null || json.isBlank()) {
            return MissingNode.getInstance();
        }
        try {
            return objectMapper.readTree(json);
        } catch (JsonProcessingException e) {
            throw parseFailed(e);
        }
    }

    /** jsonb 문자열을 타입으로 읽는다. null·빈 문자열은 null */
    public <T> T read(String json, Class<T> type) {
        if (json == null || json.isBlank()) {
            return null;
        }
        try {
            return objectMapper.readValue(json, type);
        } catch (JsonProcessingException e) {
            throw parseFailed(e);
        }
    }

    /** 제네릭 타입(List, Map 등)으로 읽는다. null·빈 문자열은 null */
    public <T> T read(String json, TypeReference<T> type) {
        if (json == null || json.isBlank()) {
            return null;
        }
        try {
            return objectMapper.readValue(json, type);
        } catch (JsonProcessingException e) {
            throw parseFailed(e);
        }
    }

    /** 트리를 원하는 타입으로 바꾼다. 응답 DTO 로 옮길 때 쓴다 */
    public <T> T convert(JsonNode node, Class<T> type) {
        if (node == null || node.isMissingNode() || node.isNull()) {
            return null;
        }
        try {
            return objectMapper.treeToValue(node, type);
        } catch (JsonProcessingException e) {
            throw parseFailed(e);
        }
    }

    /** 객체(JsonNode 포함)를 jsonb 에 넣을 문자열로 쓴다. null 은 null (컬럼을 NULL 로 둔다) */
    public String write(Object value) {
        if (value == null) {
            return null;
        }
        try {
            return objectMapper.writeValueAsString(value);
        } catch (JsonProcessingException e) {
            log.error("[Json] 직렬화 실패: type={}, message={}", value.getClass().getName(), e.getOriginalMessage());
            throw new BusinessException(ErrorCode.INTERNAL_ERROR);
        }
    }

    private BusinessException parseFailed(JsonProcessingException e) {
        // 원문은 개인 정보가 섞일 수 있어 남기지 않는다
        log.error("[Json] 파싱 실패: {}", e.getOriginalMessage());
        return new BusinessException(ErrorCode.INTERNAL_ERROR);
    }
}
