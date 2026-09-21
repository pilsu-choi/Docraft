import AppKit
import Vision

enum ConversionError: Error { case usage, image }

do {
    guard CommandLine.arguments.count == 3 else { throw ConversionError.usage }
    let source = CommandLine.arguments[1]
    let output = URL(fileURLWithPath: CommandLine.arguments[2])
    guard let image = NSImage(contentsOfFile: source), let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        throw ConversionError.image
    }
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.recognitionLanguages = ["ko-KR", "en-US"]
    request.usesLanguageCorrection = true
    try VNImageRequestHandler(cgImage: cgImage).perform([request])
    let lines = (request.results ?? []).compactMap { observation -> [String: Any]? in
        guard let text = observation.topCandidates(1).first?.string.trimmingCharacters(in: .whitespacesAndNewlines), !text.isEmpty else { return nil }
        let box = observation.boundingBox
        return ["text": text, "x": box.minX, "y": box.minY, "width": box.width, "height": box.height]
    }
    let payload: [String: Any] = ["width": cgImage.width, "height": cgImage.height, "lines": lines]
    try JSONSerialization.data(withJSONObject: payload).write(to: output)
    FileHandle.standardError.write(Data("recognized-lines=\(lines.count)\n".utf8))
} catch ConversionError.usage {
    FileHandle.standardError.write(Data("usage: vision_ocr_lines <input.png> <output.json>\n".utf8))
    exit(64)
} catch {
    FileHandle.standardError.write(Data("vision OCR failed\n".utf8))
    exit(1)
}
