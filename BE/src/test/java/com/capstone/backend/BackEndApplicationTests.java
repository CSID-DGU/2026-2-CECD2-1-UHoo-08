package com.capstone.backend;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.boot.test.context.SpringBootTest;

/**
 * 엔티티와 실제 스키마가 맞는지 확인한다(ddl-auto: validate). DB 가 있어야 해서 접속 주소가 없는 CI 에서는 건너뛴다.
 */
@SpringBootTest
@EnabledIfEnvironmentVariable(named = "SPRING_DATASOURCE_URL", matches = ".+")
class BackEndApplicationTests {

    @Test
    void contextLoads() {
    }

}
