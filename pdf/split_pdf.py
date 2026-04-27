#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

import fitz  # PyMuPDF


def split_pdf_to_images(pdf_path: str, output_folder: str | None = None, dpi: int = 200) -> int:
    pdf_file = Path(pdf_path).expanduser().resolve()
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF 文件不存在: {pdf_file}")
    if not pdf_file.is_file():
        raise ValueError(f"不是有效文件: {pdf_file}")
    if pdf_file.suffix.lower() != ".pdf":
        raise ValueError(f"文件不是 PDF: {pdf_file}")
    if dpi <= 0:
        raise ValueError(f"dpi 必须大于 0，当前值: {dpi}")

    output_dir = Path(output_folder).expanduser().resolve() if output_folder else pdf_file.with_name(f"{pdf_file.stem}_images")
    output_dir.mkdir(parents=True, exist_ok=True)

    with fitz.open(pdf_file) as doc:
        total_pages = len(doc)
        if total_pages == 0:
            raise ValueError(f"PDF 没有可处理页面: {pdf_file}")

        for page_num in range(total_pages):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=dpi)
            img_path = output_dir / f"page_{page_num + 1:04d}.png"
            pix.save(img_path)
            print(f"已保存：{img_path}")

    print(f"\n完成！共切分 {total_pages} 页，保存在 {output_dir}/")
    return total_pages


def main() -> None:
    parser = argparse.ArgumentParser(description="将 PDF 按页拆分为 PNG 图片")
    parser.add_argument("pdf", help="PDF 文件路径")
    parser.add_argument("output", nargs="?", help="输出目录，默认 <PDF文件名>_images")
    parser.add_argument("--dpi", type=int, default=200, help="输出图片 DPI，默认 200")

    args = parser.parse_args()

    try:
        split_pdf_to_images(args.pdf, args.output, dpi=args.dpi)
    except Exception as exc:
        print(f"错误：{exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
