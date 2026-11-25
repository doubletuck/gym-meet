// OCR page images with macOS's Vision framework, one word per line with its box, for ocr_draft.py.
//
// Usage (macOS; render the pages first, e.g. `pdftoppm -r 220 -png book.pdf <scratch>/pages/p`):
//
//     swiftc -O ocr_pages.swift -o <scratch>/ocr_pages
//     <scratch>/ocr_pages [--fast] <scratch>/ocr <scratch>/pages/*.png
//
// Writes <out_dir>/<image name>.tsv with one row per word: x0, y0, x1, y1 (pixels, top-left origin),
// confidence, text. `--fast` uses Vision's fast recognizer: on some tables (the 2026 African
// Championships' outlined text) the accurate one drops whole columns of numbers that the fast one
// reads, while the fast one drops lone characters (ranks, Q). Run both into two folders and combine
// them with `ocr_draft.py merge`. See docs/instructions-results-parsing.md §2.3.
import AppKit
import Foundation
import Vision

var args = CommandLine.arguments
let fast = args.count > 1 && args[1] == "--fast"
if fast {
    args.remove(at: 1)
}
guard args.count > 2 else {
    print("usage: ocr_pages [--fast] <out_dir> <image>...")
    exit(2)
}
let outDir = args[1]
for path in args[2...] {
    guard let image = NSImage(contentsOfFile: path),
          let cg = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        print("cannot read \(path)")
        continue
    }
    let width = Double(cg.width), height = Double(cg.height)
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = fast ? .fast : .accurate
    request.usesLanguageCorrection = false      // scores and names, not prose
    if !fast {
        request.recognitionLanguages = ["en-US", "es-ES", "pt-BR"]
    }
    try VNImageRequestHandler(cgImage: cg, options: [:]).perform([request])
    var out = ""
    for observation in request.results ?? [] {
        guard let candidate = observation.topCandidates(1).first else { continue }
        // Vision groups words into runs; split them so each word keeps its own column position
        let text = candidate.string
        var start = text.startIndex
        while start < text.endIndex {
            while start < text.endIndex && text[start] == " " { start = text.index(after: start) }
            if start >= text.endIndex { break }
            var end = start
            while end < text.endIndex && text[end] != " " { end = text.index(after: end) }
            let box = (try? candidate.boundingBox(for: start..<end))?.boundingBox ?? observation.boundingBox
            out += String(format: "%.0f\t%.0f\t%.0f\t%.0f\t%.2f\t", box.minX * width, (1 - box.maxY) * height,
                          box.maxX * width, (1 - box.minY) * height, candidate.confidence)
            out += text[start..<end] + "\n"
            start = end
        }
    }
    try out.write(toFile: outDir + "/" + (path as NSString).lastPathComponent + ".tsv", atomically: true,
                  encoding: .utf8)
}
