-- 037_drop_registered_products_view.sql
--
-- 036 에서 남긴 옛 이름의 뷰 registered_products 를 지운다.
--
-- 뷰는 테이블 이름을 바꾼 뒤 새 BE 가 배포될 때까지 옛 BE 가 쓰도록 둔 것이다. 새 BE 가 운영에 배포되어
-- 더는 쓰는 곳이 없다. 남겨 두면 같은 데이터가 두 이름으로 보여 다시 헷갈린다.
-- 데이터는 frequently_used_products 에 그대로 있다. 여러 번 실행해도 결과가 같다.

-- 뷰를 지우는 동안 뷰를 잠근다. 다른 작업이 잠금을 오래 쥐고 있으면 기다리지 않고 실패하게 한다.
SET lock_timeout = '5s';

DROP VIEW IF EXISTS registered_products;

RESET lock_timeout;
