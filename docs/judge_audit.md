# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n   | κ     | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|-----|-------|-----------|--------|-----------------------------------|---|
| tone_ok | 100 | 0.757 | 0.857     | 0.8    | Đạt                               | dùng |
| helpful | 100 | 0.375 | 1         | 0.3    | Không đạt                         | loại |

## ≥5 case audit thủ công
| # | Case   | Judge nói | Người nói | Ai đúng? | Ghi chú / hành động sửa rubric                                                                                                                                                                   |
|---|--------|-----------|-----------|----------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1 | H-008  | PASS      | FAIL      | Người    | Judge đang dung thứ cho giọng quá suồng sã. Nêu rõ trong rubric rằng “em”, “nha”, “check giúp em” không phù hợp với giọng CS chuẩn trong ngữ cảnh này; ưu tiên cách xưng hô lịch sự, trung tính. |
| 2 | H-017  | PASS      | FAIL      | Người    | CSV ghi khách là người lớn tuổi và đánh dấu cách gọi “bạn” là quá suồng sã. Bổ sung quy tắc chọn đại từ theo ngữ cảnh/đối tượng khách; không suy đoán tuổi nếu dữ liệu không cung cấp.           |
| 3 | H-051  | FAIL      | PASS      | Người    | CSV xác nhận CS LogiX cho phép từ “refund”. Không được tự động trừ điểm chỉ vì có từ tiếng Anh được phép; thêm danh sách thuật ngữ được chấp nhận vào rubric.                                    |
| 4 | HL-020 | PASS      | FAIL      | Người    | Ghi chú CSV xác nhận 90.000đ sai với ledger 120.000đ. Helpful cần bao gồm tính đúng đắn của thông tin giao dịch; đối chiếu số tiền trong reply với ledger và đánh FAIL khi lệch.                 |
| 5 | H-042  | FAIL      | PASS      | Người    | Câu trả lời ngắn nhưng đủ thông tin theo ghi chú CSV. Không bắt buộc xin lỗi khi không có sự cố cần xin lỗi; chấm tone theo lịch sự, rõ ràng và phù hợp ngữ cảnh.                                |

## Kết luận
- **Dùng `tone_ok` làm tín hiệu gate có giám sát**, vì đạt cả ba floor (κ=0.757, precision=0.857, recall=0.8). Ma trận nhầm lẫn là TP=24, FP=4, FN=6, TN=66: judge bắt được 24/30 lỗi tone, nhưng vẫn bỏ sót 6 lỗi và gắn nhầm 4 câu đạt thành lỗi. Cần giữ các quy tắc rubric về xưng hô theo ngữ cảnh, thuật ngữ được phép và không bắt buộc xin lỗi khi không cần.
- **Loại `helpful` khỏi gate.** Ma trận là TP=9, FP=0, FN=21, TN=70; precision=1.0 nhưng recall chỉ 0.3 và κ=0.375. Judge không gắn nhầm FAIL trong mẫu này nhưng bỏ lọt 21/30 lỗi, nên câu trả lời không hữu ích có thể được cho qua. Ví dụ HL-020 cho thấy cần chấm cả độ đúng của thông tin giao dịch và đối chiếu số tiền với ledger.
- **Rủi ro còn lại:** hai judge chỉ được đánh giá trên 100 dòng replay công khai; kết quả chưa chứng minh khả năng tổng quát hóa sang dữ liệu mới. Cần thu thập nhãn người độc lập trên một tập held-out mới, rà soát bất đồng, rồi hiệu chuẩn lại trước khi mở rộng phạm vi sử dụng. Rogan–Gladen ước tính tỉ lệ lỗi helpful là 0.30 từ mức quan sát 0.09, nhưng không làm judge đủ tin cậy để làm gate.
