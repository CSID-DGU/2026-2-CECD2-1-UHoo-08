package com.capstone.backend.domain.recommendation.service;

import com.capstone.backend.domain.recommendation.service.BundleSnapshotReader.BundleSlot;
import com.capstone.backend.domain.recommendation.service.BundleSnapshotReader.Candidate;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.MissingNode;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.io.InputStream;

import static org.assertj.core.api.Assertions.assertThat;

class BundleSnapshotReaderTest {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private static JsonNode sample() throws IOException {
        try (InputStream in = BundleSnapshotReaderTest.class.getResourceAsStream("/ai-results/S6_BUNDLE_SNAPSHOT.json")) {
            return MAPPER.readTree(in);
        }
    }

    @Test
    void 샘플의_칸과_후보를_읽는다() throws IOException {
        assertThat(BundleSnapshotReader.slots(sample())).extracting(BundleSlot::slotKey).containsExactly("toner", "serum");

        BundleSlot toner = BundleSnapshotReader.find(sample(), "toner").orElseThrow();
        assertThat(toner.label()).isEqualTo("토너");
        assertThat(toner.candidates()).containsExactly(
                new Candidate("11111111-1111-1111-1111-111111111111", "그린티 토너", 22000, 80),
                new Candidate("44444444-4444-4444-4444-444444444444", "순한 토너", 15000, 72));
    }

    @Test
    void 없는_칸_키면_비어_있다() throws IOException {
        assertThat(BundleSnapshotReader.find(sample(), "cream")).isEmpty();
    }

    @Test
    void 블록이_없거나_모양이_잘못되면_후보가_없다() throws IOException {
        assertThat(BundleSnapshotReader.slots(MissingNode.getInstance())).isEmpty();
        assertThat(BundleSnapshotReader.slots(MAPPER.readTree("{}"))).isEmpty();
        assertThat(BundleSnapshotReader.slots(MAPPER.readTree("{\"bundle_slots\":\"toner\"}"))).isEmpty();
        assertThat(BundleSnapshotReader.slots(MAPPER.readTree("{\"bundle_slots\":[\"toner\",{\"label\":\"토너\"},{\"slotKey\":\" \"}]}"))).isEmpty();
    }

    @Test
    void 제품_id나_가격을_모르는_후보는_뺀다() throws IOException {
        JsonNode snapshot = MAPPER.readTree("""
                {"bundle_slots":[{"slotKey":"toner","label":"토너","candidates":[
                  {"productId":"p1","name":"가격 없음","score":80},
                  {"productId":"p2","name":"가격 null","price":null,"score":80},
                  {"productId":"p3","name":"가격 문자","price":"1000","score":80},
                  {"productId":"p4","name":"가격 음수","price":-1,"score":80},
                  {"name":"id 없음","price":1000,"score":80},
                  {"productId":"p5","name":"무료","price":0,"score":80},
                  {"productId":"p6","name":"점수 없음","price":1000}
                ]}]}
                """);

        assertThat(BundleSnapshotReader.find(snapshot, "toner").orElseThrow().candidates()).containsExactly(
                new Candidate("p5", "무료", 0, 80),
                new Candidate("p6", "점수 없음", 1000, null));
    }

    @Test
    void 후보_블록이_없는_칸은_후보가_비어_있고_칸_이름이_없으면_칸_키로_둔다() throws IOException {
        BundleSlot slot = BundleSnapshotReader.find(MAPPER.readTree("{\"bundle_slots\":[{\"slotKey\":\"toner\"}]}"), "toner").orElseThrow();

        assertThat(slot.label()).isEqualTo("toner");
        assertThat(slot.candidates()).isEmpty();
    }
}
