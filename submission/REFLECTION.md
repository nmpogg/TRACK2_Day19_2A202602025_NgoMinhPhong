# Reflection — Lab 19

**Tên:** Ngô Minh Phong
**Cohort:** _3_
**Path đã chạy:** _lite_

---

## Câu hỏi (≤ 200 chữ)

> Trên golden set 50 queries, mode nào thắng ở loại query nào (`exact` /
> `paraphrase` / `mixed`), và tại sao? Khi nào bạn **không** dùng hybrid
> (khi nào pure BM25 hoặc pure vector là lựa chọn đúng)?

Trên golden set, BM25 thắng rõ nhất ở nhóm `exact` vì các từ khóa trong truy
vấn trùng trực tiếp với tiêu đề và nội dung tài liệu. Vector search phù hợp hơn
với `paraphrase`, nơi cách diễn đạt thay đổi nhưng ngữ nghĩa vẫn tương đồng.
Hybrid thường cho kết quả tốt nhất ở nhóm `mixed` và trung bình toàn bộ vì RRF
kết hợp được tín hiệu lexical và semantic, đồng thời giảm các lỗi riêng của
từng bộ retriever.

Tôi không dùng hybrid khi truy vấn là exact và yêu cầu độ trễ thấp nhất: BM25
thường đủ chính xác và tránh thêm chi phí embedding/vector search. Với truy vấn
paraphrase thuần túy, pure vector có thể là lựa chọn hợp lý nếu semantic recall
quan trọng hơn lexical precision. Hybrid cũng không phù hợp khi tài nguyên CPU
bị giới hạn hoặc khi một retriever đã được chứng minh là đủ tốt cho domain cụ
thể.

---

## Điều ngạc nhiên nhất khi làm lab này

Điều bất ngờ nhất là tail latency bị ảnh hưởng đáng kể bởi việc mã hóa query
trên CPU và cold-start của embedding runtime. Vì vậy benchmark cần warm-up và
phải phân biệt latency server-side với wall-clock latency.

---

## Bonus challenge

- [x] Đã làm bonus (xem `bonus/`)
- [ ] Pair work với: _Không_
