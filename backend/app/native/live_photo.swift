import Foundation
import AVFoundation
import ImageIO
import UniformTypeIdentifiers
import AppKit
import Photos

// Local file conversion only. No Photos library access or network requests.
struct ConversionError: Error { let message: String }
func require(_ condition: Bool, _ message: String) throws {
    if !condition { throw ConversionError(message: message) }
}

func writePhoto(_ source: URL, _ destination: URL, _ identifier: String) throws {
    guard let image = CGImageSourceCreateWithURL(source as CFURL, nil),
          let output = CGImageDestinationCreateWithURL(destination as CFURL, UTType.jpeg.identifier as CFString, 1, nil)
    else { throw ConversionError(message: "Unable to open image") }
    var properties = (CGImageSourceCopyPropertiesAtIndex(image, 0, nil) as? [String: Any]) ?? [:]
    var maker = (properties[kCGImagePropertyMakerAppleDictionary as String] as? [String: Any]) ?? [:]
    maker["17"] = identifier
    properties[kCGImagePropertyMakerAppleDictionary as String] = maker
    properties[kCGImageDestinationLossyCompressionQuality as String] = 0.98
    CGImageDestinationAddImageFromSource(output, image, 0, properties as CFDictionary)
    try require(CGImageDestinationFinalize(output), "Unable to write paired JPEG")
}

func writeMovie(_ source: URL, _ destination: URL, _ identifier: String) throws {
    let asset = AVURLAsset(url: source)
    let duration = asset.duration
    try require(duration.isNumeric && duration.seconds > 0, "Invalid movie duration")
    let reader = try AVAssetReader(asset: asset)
    let writer = try AVAssetWriter(outputURL: destination, fileType: .mov)
    let contentID = AVMutableMetadataItem()
    contentID.identifier = .quickTimeMetadataContentIdentifier
    contentID.value = identifier as NSString
    contentID.dataType = kCMMetadataBaseDataType_UTF8 as String
    writer.metadata = [contentID]

    var pairs: [(AVAssetReaderTrackOutput, AVAssetWriterInput)] = []
    for track in asset.tracks where track.mediaType == .video || track.mediaType == .audio {
        let output = AVAssetReaderTrackOutput(track: track, outputSettings: nil)
        output.alwaysCopiesSampleData = false
        guard let format = track.formatDescriptions.first else { continue }
        let input = AVAssetWriterInput(mediaType: track.mediaType, outputSettings: nil,
                                      sourceFormatHint: (format as! CMFormatDescription))
        input.expectsMediaDataInRealTime = false
        if track.mediaType == .video { input.transform = track.preferredTransform }
        try require(reader.canAdd(output) && writer.canAdd(input), "Unsupported movie track")
        reader.add(output)
        writer.add(input)
        pairs.append((output, input))
    }
    try require(pairs.contains { $0.1.mediaType == .video }, "Movie has no video track")

    let stillKey = "mdta/com.apple.quicktime.still-image-time"
    let spec: [String: Any] = [
        kCMMetadataFormatDescriptionMetadataSpecificationKey_Identifier as String: stillKey,
        kCMMetadataFormatDescriptionMetadataSpecificationKey_DataType as String: kCMMetadataBaseDataType_SInt8
    ]
    var description: CMMetadataFormatDescription?
    let status = CMMetadataFormatDescriptionCreateWithMetadataSpecifications(
        allocator: kCFAllocatorDefault, metadataType: kCMMetadataFormatType_Boxed,
        metadataSpecifications: [spec] as CFArray, formatDescriptionOut: &description)
    try require(status == noErr && description != nil, "Unable to create metadata format")
    let metadataInput = AVAssetWriterInput(mediaType: .metadata, outputSettings: nil, sourceFormatHint: description)
    let adaptor = AVAssetWriterInputMetadataAdaptor(assetWriterInput: metadataInput)
    try require(writer.canAdd(metadataInput), "Unable to add timed metadata")
    writer.add(metadataInput)
    try require(writer.startWriting() && reader.startReading(), "Unable to start movie conversion")
    writer.startSession(atSourceTime: .zero)

    let still = AVMutableMetadataItem()
    still.keySpace = .quickTimeMetadata
    still.key = "com.apple.quicktime.still-image-time" as NSString
    still.value = NSNumber(value: Int8(0))
    still.dataType = kCMMetadataBaseDataType_SInt8 as String
    // Web exports do not include the capture's key-photo timestamp. Use the
    // midpoint, retaining the source photo and the complete motion clip.
    let range = CMTimeRange(start: CMTime(seconds: duration.seconds / 2, preferredTimescale: 600),
                            duration: CMTime(value: 1, timescale: 600))
    try require(adaptor.append(AVTimedMetadataGroup(items: [still], timeRange: range)), "Unable to write still-image-time")
    metadataInput.markAsFinished()

    let group = DispatchGroup()
    for (index, pair) in pairs.enumerated() {
        let (output, input) = pair
        group.enter()
        var finished = false
        input.requestMediaDataWhenReady(on: DispatchQueue(label: "live-photo.track.\(index)")) {
            guard !finished else { return }
            while input.isReadyForMoreMediaData {
                if let sample = output.copyNextSampleBuffer() {
                    if !input.append(sample) {
                        finished = true
                        input.markAsFinished()
                        group.leave()
                        return
                    }
                } else {
                    finished = true
                    input.markAsFinished()
                    group.leave()
                    return
                }
            }
        }
    }
    try require(group.wait(timeout: .now() + 110) == .success, "Movie conversion timed out")
    try require(reader.status == .completed, "Unable to read all movie samples")
    let done = DispatchSemaphore(value: 0)
    writer.finishWriting { done.signal() }
    try require(done.wait(timeout: .now() + 20) == .success && writer.status == .completed, "Unable to finalize paired movie")
}

func inspectPair(_ photo: URL, _ movie: URL) throws -> [String: Any] {
    guard let source = CGImageSourceCreateWithURL(photo as CFURL, nil),
          let properties = CGImageSourceCopyPropertiesAtIndex(source, 0, nil) as? [String: Any],
          let maker = properties[kCGImagePropertyMakerAppleDictionary as String] as? [String: Any],
          let photoID = maker["17"] as? String else { throw ConversionError(message: "Missing photo identifier") }
    let asset = AVURLAsset(url: movie)
    let movieID = asset.metadata.first { $0.identifier == .quickTimeMetadataContentIdentifier }?.stringValue
    try require(movieID == photoID, "Photo and movie identifiers differ")
    let reader = try AVAssetReader(asset: asset)
    guard let track = asset.tracks(withMediaType: .metadata).first else { throw ConversionError(message: "Missing timed metadata track") }
    let output = AVAssetReaderTrackOutput(track: track, outputSettings: nil)
    reader.add(output)
    try require(reader.startReading(), "Unable to read timed metadata")
    var stillTime: Double?
    while let sample = output.copyNextSampleBuffer() {
        if let metadata = AVTimedMetadataGroup(sampleBuffer: sample),
           metadata.items.contains(where: { $0.identifier?.rawValue == "mdta/com.apple.quicktime.still-image-time" }) {
            stillTime = metadata.timeRange.start.seconds
        }
    }
    try require(stillTime != nil, "Missing still-image-time sample")
    return ["identifier": photoID, "still_image_time": stillTime!, "duration": asset.duration.seconds]
}

func validateWithPhotos(_ photo: URL, _ movie: URL) throws {
    let lock = NSLock()
    var finished = false
    var accepted = false
    PHLivePhoto.request(withResourceFileURLs: [photo, movie], placeholderImage: nil,
                        targetSize: .zero, contentMode: .aspectFit) { live, info in
        if (info[PHLivePhotoInfoIsDegradedKey] as? Bool) != true {
            lock.lock()
            accepted = live != nil
            finished = true
            lock.unlock()
        }
    }
    let deadline = Date().addingTimeInterval(25)
    while Date() < deadline {
        lock.lock()
        let done = finished
        lock.unlock()
        if done { break }
        RunLoop.current.run(until: Date().addingTimeInterval(0.05))
    }
    lock.lock()
    let valid = accepted
    lock.unlock()
    try require(valid, "Photos did not recognize the Live Photo pair")
}

do {
    let args = CommandLine.arguments
    try require(args.count >= 4, "Usage: pair image video stem | inspect jpg mov | validate jpg mov")
    if args[1] == "pair" {
        try require(args.count == 5, "Missing output stem")
        let photo = URL(fileURLWithPath: args[4] + ".jpg")
        let movie = URL(fileURLWithPath: args[4] + ".mov")
        let identifier = UUID().uuidString
        try writePhoto(URL(fileURLWithPath: args[2]), photo, identifier)
        try writeMovie(URL(fileURLWithPath: args[3]), movie, identifier)
        let result = try inspectPair(photo, movie)
        try validateWithPhotos(photo, movie)
        print(String(data: try JSONSerialization.data(withJSONObject: result), encoding: .utf8)!)
    } else if args[1] == "inspect" || args[1] == "validate" {
        let photo = URL(fileURLWithPath: args[2]), movie = URL(fileURLWithPath: args[3])
        let result = try inspectPair(photo, movie)
        if args[1] == "validate" { try validateWithPhotos(photo, movie) }
        print(String(data: try JSONSerialization.data(withJSONObject: result), encoding: .utf8)!)
    } else { throw ConversionError(message: "Unknown command") }
} catch {
    // Fixed diagnostics only: input paths and source metadata are not logged.
    let message = (error as? ConversionError)?.message ?? "Live Photo conversion failed"
    FileHandle.standardError.write(Data((message + "\n").utf8))
    exit(1)
}
