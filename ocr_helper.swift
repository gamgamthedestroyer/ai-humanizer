import Vision
import AppKit
import Foundation

guard CommandLine.arguments.count > 1 else {
    fputs("Usage: ocr_helper <image_path>\n", stderr)
    exit(1)
}

let path = CommandLine.arguments[1]
guard let nsImage = NSImage(contentsOfFile: path) else {
    fputs("Cannot load image: \(path)\n", stderr)
    exit(1)
}

var rect = NSRect.zero
guard let cgImage = nsImage.cgImage(forProposedRect: &rect, context: nil, hints: nil) else {
    fputs("Cannot get CGImage\n", stderr)
    exit(1)
}

let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = true

let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
do {
    try handler.perform([request])
} catch {
    fputs("Vision error: \(error)\n", stderr)
    exit(1)
}

var output: [[String: Any]] = []
for obs in (request.results ?? []) {
    guard let cand = obs.topCandidates(1).first else { continue }
    let bb = obs.boundingBox
    output.append([
        "t": cand.string,
        "x": bb.origin.x,
        "y": bb.origin.y,
        "w": bb.size.width,
        "h": bb.size.height
    ])
}

let jsonData = try! JSONSerialization.data(withJSONObject: output, options: [])
print(String(data: jsonData, encoding: .utf8)!)
