"""Five-query demonstration for the hybrid memory agent."""
import sys

from agent import HybridMemoryAgent


def main() -> None:
    # Windows terminals may default to cp1258, which cannot print every
    # Vietnamese combining character used by the demo data.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    agent = HybridMemoryAgent()
    memories = [
        "Tôi đã đọc Kubernetes Horizontal Pod Autoscaler. HPA tự động tăng hoặc giảm pod theo CPU và memory.",
        "Tài liệu Terraform giải thích infrastructure as code và cách quản lý cloud resources bằng module.",
        "Ghi chú cloud security: dùng least privilege IAM, mã hóa dữ liệu và xoay vòng secrets định kỳ.",
        "Tôi thích tài liệu cloud và DevOps bằng tiếng Việt, nhưng giữ nguyên thuật ngữ kỹ thuật tiếng Anh.",
        "Bài viết về autoscaling hạ tầng mô tả scale-out khi tải tăng và scale-in khi lưu lượng giảm.",
    ]
    for memory in memories:
        agent.remember(memory)

    queries = [
        "Tôi đã đọc gì về Kubernetes?",
        "Recommend đọc gì tiếp",
        "Tôi đang quan tâm gì gần đây?",
        "Tài liệu về tự động mở rộng hạ tầng?",
        "Cho tôi summary cloud security",
    ]
    for number, query in enumerate(queries, 1):
        print(f"\n=== Query {number}: {query} ===")
        print(agent.recall(query))


if __name__ == "__main__":
    main()
