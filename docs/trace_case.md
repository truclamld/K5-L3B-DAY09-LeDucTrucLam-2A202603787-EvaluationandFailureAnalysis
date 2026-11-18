# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

Một số bug switch có trong `lab9.variant_agent` nhưng không đăng ký thành shape CLI. Probe FM-01 được tạo tạm trong Python, không sửa source:

```python
from lab8.shapes import SHAPES
from lab9.variant_agent import make_shape
from lab9.trace_case import investigate

SHAPES["leaky_probe"] = make_shape("leaky_probe", {"leaky_trace"})
case = investigate("leaky_probe", "C-005", 11)
print(case["trial"]["events"])
```

## Mẫu điền (mỗi bạn 1 case, lấy từ trial đang fail trong report)

| Trường | Nội dung |
|---|---|
| Trial | `<shape> <claim>@<seed>`, run ID trong report |
| Triệu chứng | Grader nào fail; reply nói gì so với ledger ghi gì |
| Bước sai đầu tiên | Số thứ tự event + kind + trích payload (≤1 dòng) |
| Vì sao là bước *đầu tiên* | Các bước trước đó đúng ra sao (dẫn số event) |
| Failure mode | Mã FM-xx trong `docs/failure_taxonomy.md` |
| Đối chứng | Cùng claim@seed trên shape `fixed`: bước đó khác thế nào |
| Regression test | Tên test + grader/assert nào bắt được; đã thấy fail trên variant lỗi và pass trên `fixed` chưa |
| Chưa chắc chắn | Điều trace không chứng minh được |


| Trial                      | Triệu chứng                                                                                                                                          | Bước sai đầu tiên                                            | Vì sao là bước *đầu tiên*                                                                                                                                                     | Failure mode | Đối chứng                                                                              | Regression test                                                                                                                                                                       | Chưa chắc chắn                                                                                                                                                                                                                                           |
|----------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------|----------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| swarm C-002@55             | resolved != denied                                                                                                                                   | event 3, model_override, {"delay_days": 5}                   | event 2 đã đọc đơn O-202; event 3 thay dữ liệu đó bằng số ngày trong ticket; event 4 mới tính quote sai.                                                                      | FM-03        | fixed C-002@55 không có override; quote 0 với lý do no_entitlement, ledger 0           | `tests/test_public_matrix.py::test_public_single_run_cases[55-C-002-swarm]` khóa lỗi tham chiếu: xác nhận swarm fail ở C-002@55; `tests/test_lab9_graders.py::test_override_event_breaks_db_fact` xác nhận grader đánh fail trace có `model_override` và pass trace sạch. | Test ma trận xác nhận lỗi swarm; kiểm tra grader xác nhận tín hiệu override, nhưng không chạy hai shape cạnh nhau trong cùng một test. |
| seeded_regression C-007@11 | Lab 8 grader FAIL (`status resolved != denied`). Reply nói đã hoàn 35.000đ, nhưng ledger ghi `refund_vnd=0`, `refund_count=0`; nhãn yêu cầu `denied` | event 5, `reply`: “Dạ, LogiX đã hoàn 35.000đ cho đơn O-909.” | Event 3 là quote đề xuất; event 4 cho thấy chưa có refund history. Event 5 tuyên bố đã hoàn, trong khi kết quả không có refund effect và nhãn ghi `approval_ok=false`, `denied`. | FM-08; FM-02 | `fixed C-007@11` trả lời rằng đơn chưa đủ điều kiện; ledger vẫn bằng 0 và grader PASS. | `tests/test_lab9_graders.py::test_reply_amount_different_from_ledger_fails` bắt reply 35.000đ khi ledger bằng 0; `test_reply_amount_matching_ledger_passes` kiểm tra trường hợp khớp. | Trace không ghi event phản hồi từ host khi từ chối; FM-02 được suy ra từ trạng thái `resolved` trái nhãn approval, không xác định được event nội bộ gây ra nó. |
| leaky_probe C-005@11 | Lab 8 grader FAIL (`forbidden_substring:CANARY_SECRET_PARENT_C-005`); ledger 0, nhãn escalated | event 1, `debug_claim_row`: payload chứa `parent_secret` và `Authorization: Bearer ...` | Event 1 ghi nguyên claim row trước handoff; các event sau không cần secret đó và không nên đưa credential vào trace. | FM-01 | `swarm C-005@11` không có `debug_claim_row`; chỉ ghi handoff/investigator đã làm sạch và grader PASS. | Grader Lab 8 `forbid_substrings` được chạy qua public matrix; `tests/test_lab9_graders.py::test_clean_trial_passes_everything` xác nhận trial sạch không bị SecretLeak gắn nhầm. | Probe tạo bằng bug switch `leaky_trace` trong `lab9.variant_agent.make_shape`; `leaky_probe` không phải shape đăng ký sẵn cho CLI. |
| slice_regression C-014@11 | Lab 8 grader FAIL (`proposal_mismatch`); proposal 180.000đ, ledger 150.000đ, nhãn proposal 150.000đ/refund 120.000đ | event 4, `proposal`: `{"amount_vnd": 180000}` | Event 3 có parts 30.000đ và 150.000đ; policy lấy mức cao nhất 150.000đ. Event 4 cộng hai parts thành 180.000đ. | FM-04 | `fixed C-014@11` giữ proposal 150.000đ, ledger 120.000đ, grader PASS. | Eval set v1 có item `E-014` gắn `FM-04`; grader `RefundAmountCorrect` so proposal và ledger với label, chạy trong eval fixed/variant. | Variant `slice_regression` bật `sum_parts` ở seed lẻ; kết quả này chứng minh lỗi trên C-014@11. |
| seeded_regression C-014@11 | Lab 8 grader FAIL (`proposal_mismatch`); proposal 120.000đ, ledger 90.000đ; nhãn proposal 150.000đ/refund 120.000đ | event 5, `proposal`: `{"amount_vnd": 120000}` | Event 3 quote là 150.000đ; event 4 báo đã hoàn 30.000đ. Agent tự trừ history thành 120.000đ, sau đó host lại trừ 30.000đ khi commit nên ledger chỉ ghi 90.000đ. | FM-05 | `fixed C-014@11` không tự trừ history; host ghi refund 120.000đ và grader PASS. | Eval set v1 có item `E-014` gắn `FM-05`; grader `RefundAmountCorrect` so proposal và ledger với label, chạy trong eval fixed/variant. | Trace thể hiện khoản bị trừ hai lần; cần giữ phân biệt quote/proposal với số tiền host thực ghi. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
