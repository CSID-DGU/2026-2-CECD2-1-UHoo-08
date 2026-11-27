package com.capstone.backend.domain.product.service;

/**
 * 앞말의 받침에 맞는 조사를 고른다.
 *
 * 괄호 같은 기호는 건너뛰고 마지막 글자를 본다. 숫자와 영문은 읽는 소리로 판단하고, 읽는 소리를 모르는 글자는 받침이 없는 것으로 둔다.
 */
final class KoreanParticle {

    private static final String LATIN_WITH_FINAL_SOUND = "LMNRlmnr";
    private static final String DIGIT_WITH_FINAL_SOUND = "013678";

    private KoreanParticle() {
    }

    /** 과, 와 */
    static String and(String text) {
        return hasFinalSound(text) ? "과" : "와";
    }

    /** 은, 는 */
    static String topic(String text) {
        return hasFinalSound(text) ? "은" : "는";
    }

    private static boolean hasFinalSound(String text) {
        for (int i = text.length() - 1; i >= 0; i--) {
            char c = text.charAt(i);
            if (c >= '가' && c <= '힣') {
                return (c - '가') % 28 != 0;
            }
            if (Character.isDigit(c)) {
                return DIGIT_WITH_FINAL_SOUND.indexOf(c) >= 0;
            }
            if (Character.isLetter(c)) {
                return LATIN_WITH_FINAL_SOUND.indexOf(c) >= 0;
            }
        }
        return false;
    }
}
