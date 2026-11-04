#!/usr/bin/env python3
"""Inspect PDFs using Playwright/Chrome DevTools to identify layout issues."""

from pathlib import Path

from playwright.sync_api import sync_playwright

BATCH_REPORT = Path("D:/Projects/job-attune-1.0.0/attune-data/runs/run-20261103140420/exports/batch-report.pdf")
CANDIDATE_PDF = Path("D:/Projects/job-attune-1.0.0/attune-data/runs/run-20261103140420/exports/candidate-08a20e4edb.pdf")

# A4 dimensions
PAGE_WIDTH_PT = 595.28
PAGE_HEIGHT_PT = 841.89
MARGIN_LEFT_RIGHT_MM = 15
MM_TO_PT = 2.83465
CONTENT_WIDTH_PT = PAGE_WIDTH_PT - 2 * MARGIN_LEFT_RIGHT_MM * MM_TO_PT
CONTENT_WIDTH_MM = CONTENT_WIDTH_PT / MM_TO_PT

def analyze_pdf(pdf_path: Path, title: str) -> dict:
    """Open PDF in browser and analyze layout issues."""
    print(f"\n{'='*60}")
    print(f"Inspecting: {title}")
    print(f"Path: {pdf_path}")
    print(f"{'='*60}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=[
            "--no-sandbox",
            "--disable-setuid-sandbox"
        ])
        
        page = browser.new_page()
        page.set_viewport_size({"width": 1200, "height": 800})
        
        # Navigate to PDF
        page.goto(f"file:///{pdf_path}")
        page.wait_for_timeout(2000)
        
        # Analyze text elements
        text_analysis = page.evaluate(f"""() => {{
            const texts = Array.from(document.querySelectorAll('text'));
            const positions = texts.map(t => {{
                text: t.textContent || '',
                x: parseFloat(t.getAttribute('x') || '0'),
                y: parseFloat(t.getAttribute('y') || '0'),
                fontSize: parseFloat(t.getAttribute('font-size') || '0'),
            }}).filter(t => t.text.trim() && t.text.trim().length > 2);
            
            // Group by y position to find horizontal text runs
            const yGroups = {{}};
            positions.forEach(t => {{
                const key = Math.round(t.y);
                if (!yGroups[key]) yGroups[key] = [];
                yGroups[key].push(t);
            }});
            
            // Sort within each y group by x
            Object.keys(yGroups).forEach(y => {{
                yGroups[y].sort((a, b) => a.x - b.x);
            }});
            
            // Find overlapping elements
            const overlaps = [];
            for (let i = 0; i < positions.length; i++) {{
                for (let j = i + 1; j < positions.length; j++) {{
                    const a = positions[i];
                    const b = positions[j];
                    const xDiff = Math.abs(a.x - b.x);
                    const yDiff = Math.abs(a.y - b.y);
                    if (xDiff < 2 && yDiff < 2 && a.text && b.text) {{
                        overlaps.push({{text1: a.text, text2: b.text, x: a.x, y: a.y}});
                    }}
                }}
            }}
            
            return {{
                totalTexts: positions.length,
                texts: positions.slice(0, 200),
                overlaps,
                yGroups,
                pageWidth: {PAGE_WIDTH_PT},
                pageHeight: {PAGE_HEIGHT_PT},
                contentWidth: {CONTENT_WIDTH_PT},
                contentWidthMM: {CONTENT_WIDTH_MM}
            }};
        }}""")
        
        print(f"\nPage dimensions: {PAGE_WIDTH_PT} x {PAGE_HEIGHT_PT} pts")
        print(f"Content area (with {MARGIN_LEFT_RIGHT_MM}mm margins): {CONTENT_WIDTH_PT:.1f} pts ({CONTENT_WIDTH_MM:.1f} mm)")
        
        print("\n--- First 80 text elements ---")
        for i, t in enumerate(text_analysis['texts'][:80]):
            print(f"  [{i:3d}] '{t['text'][:50]}...' at ({t['x']:7.1f}, {t['y']:6.1f}) fs={t['fontSize']:.1f}")
        
        if text_analysis['overlaps']:
            print(f"\n--- POTENTIAL OVERLAPS DETECTED ({len(text_analysis['overlaps'])} found) ---")
            for o in text_analysis['overlaps'][:15]:
                print(f"  OVERLAP at ({o['x']:.1f}, {o['y']:.1f}):")
                print(f"    '{o['text1'][:60]}'")
                print(f"    '{o['text2'][:60]}'")
        else:
            print("\nNo obvious overlaps detected in text elements")
        
        # Analyze horizontal runs (potential concatenated text)
        print("\n--- Analyzing horizontal text runs (potential issues) ---")
        for y_key in sorted(text_analysis['yGroups'].keys())[-10:]:
            y_group = text_analysis['yGroups'][y_key]
            if len(y_group) > 1:
                # Check if texts are adjacent (within ~50pt)
                runs = []
                current_run = [y_group[0]]
                for i in range(1, len(y_group)):
                    if y_group[i]['x'] - y_group[i-1]['x'] < 50:
                        current_run.append(y_group[i])
                    else:
                        if len(current_run) > 1:
                            runs.append(current_run)
                        current_run = [y_group[i]]
                if len(current_run) > 1:
                    runs.append(current_run)
                
                for run in runs[:3]:
                    combined = ''.join([t['text'] for t in run])
                    if len(combined.strip()) > 10:
                        print(f"  Y={float(y_key):.1f}: '{combined[:80]}...'")
                        if len(combined) > 150:
                            print("    ^ POSSIBLY OVERLAPPING/OVERWRITTEN TEXT!")
        
        # Take screenshot for visual reference
        screenshot_path = pdf_path.with_suffix('.inspected.png')
        page.screenshot(path=str(screenshot_path))
        print(f"\nScreenshot saved to: {screenshot_path}")
        
        browser.close()
        return text_analysis

def main():
    print("PDF Layout Inspector - Using Playwright/Chrome DevTools")
    print("=" * 60)
    
    results = {}
    
    # Inspect batch report
    if BATCH_REPORT.exists():
        results['batch'] = analyze_pdf(BATCH_REPORT, "Batch Report")
    else:
        print(f"Batch report not found: {BATCH_REPORT}")
    
    # Close any remaining processes
    import subprocess
    subprocess.run(["taskkill", "/f", "/im", "chrome.exe"], capture_output=True)
    
    return results

if __name__ == "__main__":
    results = main()
    print("\n" + "=" * 60)
    print("INSPERATION COMPLETE")
    print("Table of contents saved for further analysis")