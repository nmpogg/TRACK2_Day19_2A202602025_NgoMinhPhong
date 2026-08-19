# Trợ lý AI có bộ nhớ — Thiết kế kiến trúc

## Mục tiêu

Mục tiêu của POC này là xây dựng một trợ lý cá nhân cho người dùng Việt Nam,
có khả năng nhớ những tài liệu và nội dung người dùng từng trao đổi. Khi thiết
kế, tôi tách dữ liệu thành ba nhóm thay vì lưu tất cả vào cùng một nơi:

- Episodic memory: hội thoại, ghi chú và tài liệu người dùng đã đọc.
- Stable profile: ngôn ngữ ưa thích, tốc độ đọc và chủ đề quan tâm.
- Recent activity: số truy vấn và các chủ đề người dùng vừa tìm kiếm gần đây.

Việc tách riêng giúp mỗi loại dữ liệu có cách lưu trữ, TTL và tốc độ cập nhật
phù hợp. Trong `agent.py`, tôi dùng vector hashing chạy trực tiếp trong bộ nhớ để
demo không cần tải model hoặc khởi động Docker. Khi triển khai thật, phần này có
thể thay bằng embedding đa ngôn ngữ và Qdrant mà không cần thay đổi interface
`remember()` và `recall()`.

## Luồng dữ liệu

```text
Tin nhắn / tài liệu của người dùng
        |
        +--> kiểm tra quyền riêng tư + chia đoạn
        |          |
        |          +--> multilingual embedding --> Qdrant
        |               payload: user_id, text, timestamp, source
        |
        +--> event stream --> query_velocity FeatureView (TTL 1 giờ)
        |
        +--> cập nhật profile --> user_profile FeatureView (TTL 30 ngày)

Truy vấn mới --> query embedding + BM25 ------------------+
                lọc payload theo user_id ------------------|--> RRF top memories
                Feast lookup: language, topic, speed ------+
                                              |
                                        dựng context --> LLM trả lời
```

Mỗi memory bắt buộc phải có `user_id`. Đây là điều kiện lọc dữ liệu, không chỉ
là một feature để xếp hạng. Context cuối cùng chỉ chứa profile, hoạt động gần
đây và ba memory liên quan nhất. Nhờ vậy LLM hiểu người đang hỏi là ai mà không
cần đưa toàn bộ lịch sử vào prompt.

## Quyết định 1 — Chia memory theo đoạn có ý nghĩa

Tôi chọn chia theo đoạn văn hoặc semantic break, mỗi chunk khoảng 80–220 token.
Chỉ khi đoạn quá dài mới cần overlap một phần nhỏ. Tôi đã cân nhắc chia theo
từng message vì cách này đơn giản và ít tốn storage, nhưng nếu người dùng dán
một tài liệu dài thì cả tài liệu sẽ thành một vector, làm mất phần nội dung cần
tìm. Chia theo toàn bộ conversation giữ được nhiều ngữ cảnh hơn, nhưng các chủ
đề không liên quan có thể bị gộp vào cùng một embedding.

Một lựa chọn khác là chia cố định 512 token. Cách này có throughput tốt và tạo
ít point hơn, nhưng không phù hợp với các tin nhắn tiếng Việt ngắn và dễ làm
lãng phí context window. Vì vậy, chunk theo đoạn là điểm cân bằng giữa chất
lượng retrieval, chi phí lưu trữ và kích thước context gửi cho LLM.

Người Việt thường viết xen kẽ Việt–Anh, đặc biệt với các từ như `autoscaling`,
`least privilege` hoặc `cloud security`. Hệ thống không nên tự dịch hay loại bỏ
các từ này khi chunk. Trong production, tôi sẽ dùng tokenizer như underthesea
hoặc pyvi kết hợp embedding đa ngôn ngữ. Demo hiện tại dùng Unicode token và
character n-gram để vẫn xử lý được dấu tiếng Việt và một số lỗi gõ đơn giản.

## Quyết định 2 — Profile dạng bảng, episodic memory dạng vector

Stable profile gồm `preferred_language`, `reading_speed_wpm` và
`topic_affinity`. Các feature này nằm trong `user_profile` FeatureView, có TTL
30 ngày và có thể cập nhật hằng ngày từ setting của người dùng hoặc thống kê
theo tuần. `queries_last_hour` và `distinct_topics_24h` thay đổi nhanh hơn nên
được đặt trong `query_velocity` FeatureView với TTL một giờ và nguồn streaming.

Tôi chọn feature dạng bảng vì dễ kiểm tra, giải thích và đưa vào prompt. Tôi đã
xem xét biểu diễn toàn bộ sở thích bằng một user embedding, nhưng không chọn vì
khó biết embedding đang đại diện cho sở thích nào, khó áp dụng TTL riêng và khó
cập nhật một thuộc tính cụ thể. Feature Store còn hỗ trợ online lookup và
point-in-time join như trong NB4, giúp tránh dùng feature tương lai khi đánh giá
offline.

Episodic memory vẫn được đặt trong vector store vì dữ liệu văn bản tăng liên
tục và cần approximate nearest-neighbor search. Profile thay đổi chậm, trong khi
memory mới có thể được thêm mỗi giờ; hai loại dữ liệu này không nên dùng chung
một chu kỳ re-index.

## Quyết định 3 — Freshness tùy theo use case

Tôi không dùng một freshness SLA chung cho mọi dữ liệu. Khi người dùng vừa đọc
xong một tài liệu, memory đó nên tìm được trong vòng dưới một giây. Vì vậy hệ
thống embed và upsert vào Qdrant ngay, đồng thời gửi activity event vào stream.

Với câu hỏi “Gần đây tôi quan tâm điều gì?”, `queries_last_hour` cần cập nhật
gần real-time và có TTL một giờ để activity cũ không ảnh hưởng kết quả. Ngược
lại, ngôn ngữ ưa thích hoặc tốc độ đọc chỉ cần batch refresh hằng ngày. Chậm năm
phút ở nhóm stable profile gần như không làm thay đổi recommendation, trong khi
streaming mọi feature sẽ tăng chi phí và độ phức tạp vận hành. Batch phù hợp với
dữ liệu ổn định; streaming chỉ dành cho dữ liệu mà độ mới thực sự thay đổi câu
trả lời hiện tại.

## Phương án đã loại và giới hạn hiện tại

Ban đầu tôi cân nhắc lưu memory, profile và recent activity trong cùng Feature
Store để kiến trúc đơn giản hơn. Tôi loại phương án này vì text embedding cần
vector search, còn profile cần schema rõ ràng, TTL và point-in-time
materialization. Gộp tất cả vào một nơi sẽ đơn giản ở bước đầu nhưng khó mở rộng
và khó kiểm soát freshness về sau.

POC hiện chưa xử lý mã hóa dữ liệu khi lưu, xóa toàn bộ dữ liệu theo yêu cầu của
người dùng, đồng bộ nhiều thiết bị, quản lý consent và xác thực Qdrant. Bản
production cần bổ sung kiểm thử tenant isolation, retention policy, encryption
at rest và dead-letter queue cho các embedding job bị lỗi. Ngoài ra cần thay
hash embedding bằng model đa ngôn ngữ thật, rồi đo riêng recall, P99 latency và
mức độ câu trả lời bám vào context.

## Ghi chú quá trình sử dụng AI

Prompt hiệu quả nhất là yêu cầu tạo interface tối thiểu gồm `remember()`,
`recall()` và demo năm truy vấn trước, sau đó mới review từng quyết định về lưu
trữ và quyền riêng tư. Một bản nháp từng đặt profile trực tiếp vào vector
payload, nhưng tôi bỏ cách đó vì nó làm lẫn lộn giữa memory và feature freshness,
đồng thời không tận dụng được typed online lookup của Feast.
