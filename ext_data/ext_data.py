from pypdf import PdfReader

def extract_pdf_core(pdf_path, output_txt_path):
    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)
    
    extracted_text = []
    # KOSHA 가이드는 통상 1~3페이지(총칙)는 버리고, 본문(4페이지 이후)부터 체크리스트 위주로 추출
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        # '목적', '적용범위'만 있는 앞부분은 건너뛰고 핵심 본문만 수집
        if "안전작업" in text or "조치기준" in text or "점검" in text:
            extracted_text.append(f"\n--- [Page {i+1}] ---\n" + text)
            
    with open(output_txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(extracted_text))
    print(f"추출 완료: {output_txt_path} (총 {len(extracted_text)}개 페이지 추출됨)")

# 실행 예시
extract_pdf_core("./data/D-C-7-2026 비계.pdf", "raw_scaffold.txt")
