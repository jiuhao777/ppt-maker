# M0 vision benchmark

The committed generator creates five deterministic synthetic 1280×720 screening images. They validate the benchmark pipeline only; they are not sufficient for model admission. Model admission requires at least 20 labeled PowerPoint-rendered pages with normal negatives and known defect classes.

Run `conda run -n AI python benchmarks/vision/generate_cases.py`. Generated PNG files remain under ignored `artifacts/m0/vision/`.
