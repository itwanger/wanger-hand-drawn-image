import AppKit
import ImageIO
import UniformTypeIdentifiers

struct Caption: Decodable { let start: Double; let end: Double; let text: String }
struct Overlay: Decodable {
  let kind: String; let start: Double; let end: Double; let color: String
  let rect: [Double]?; let points: [[Double]]?; let curve: String?
  let radius: Double?; let easing: String?; let line_width: Double?
  let keyframes: [[Double]]?; let track_color: String?
}
struct Scene: Decodable {
  let base_image: String; let fps: Int; let duration: Double
  let captions: [Caption]; let overlays: [Overlay]
  let caption_position: [Double]?; let caption_size: Double?
  let indicator_position: [Double]?
}
func color(_ hex: String) -> NSColor {
  let v = UInt32(hex.dropFirst(),radix:16)!
  return NSColor(srgbRed:Double((v>>16)&255)/255,green:Double((v>>8)&255)/255,blue:Double(v&255)/255,alpha:1)
}
func clamp(_ x: Double) -> Double { max(0,min(1,x)) }
func point(_ a: [Double]) -> CGPoint { CGPoint(x:a[0],y:a[1]) }
func lerp(_ a: CGPoint,_ b: CGPoint,_ p: Double) -> CGPoint { CGPoint(x:a.x+(b.x-a.x)*p,y:a.y+(b.y-a.y)*p) }
func curve(_ a: [CGPoint],_ p: Double) -> CGPoint {
  let q = 1-p
  return CGPoint(x:q*q*q*a[0].x+3*q*q*p*a[1].x+3*q*p*p*a[2].x+p*p*p*a[3].x,
                 y:q*q*q*a[0].y+3*q*q*p*a[1].y+3*q*p*p*a[2].y+p*p*p*a[3].y)
}
func position(_ points: [CGPoint],_ p: Double) -> CGPoint {
  let lengths = (1..<points.count).map { hypot(points[$0].x-points[$0-1].x,points[$0].y-points[$0-1].y) }
  var remaining = p*lengths.reduce(0,+)
  for i in lengths.indices {
    if remaining <= lengths[i] && lengths[i] > 0 { return lerp(points[i],points[i+1],remaining/lengths[i]) }
    remaining -= lengths[i]
  }
  return points.last!
}
func value(_ frames: [[Double]],_ time: Double) -> Double {
  if time <= frames[0][0] { return frames[0][1] }
  for i in 1..<frames.count where time <= frames[i][0] {
    let p = (time-frames[i-1][0])/(frames[i][0]-frames[i-1][0])
    return frames[i-1][1]+(frames[i][1]-frames[i-1][1])*p
  }
  return frames.last![1]
}
let configURL = URL(fileURLWithPath:CommandLine.arguments[1])
let scene = try JSONDecoder().decode(Scene.self,from:Data(contentsOf:configURL))
let frameDir = URL(fileURLWithPath:CommandLine.arguments[2])
try FileManager.default.createDirectory(at:frameDir,withIntermediateDirectories:true)
let source = CGImageSourceCreateWithURL(URL(fileURLWithPath:scene.base_image) as CFURL,nil)!
let base = CGImageSourceCreateImageAtIndex(source,0,nil)!
let width = base.width, height = base.height
let count = Int((scene.duration*Double(scene.fps)).rounded())
for frame in 0..<count {
  autoreleasepool {
    let t = Double(frame)/Double(scene.fps)
    let ctx = CGContext(data:nil,width:width,height:height,bitsPerComponent:8,bytesPerRow:width*4,
      space:CGColorSpaceCreateDeviceRGB(),bitmapInfo:CGImageAlphaInfo.premultipliedLast.rawValue)!
    ctx.draw(base,in:CGRect(x:0,y:0,width:width,height:height))
    ctx.translateBy(x:0,y:CGFloat(height));ctx.scaleBy(x:1,y:-1)
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(cgContext:ctx,flipped:true)
    for item in scene.overlays where t >= item.start && t < item.end {
      let c = color(item.color)
      let p = clamp((t-item.start)/(item.end-item.start))
      if item.kind == "bead" {
        let progress = item.easing == "linear" ? p : p*p*(3-2*p)
        let points = item.points!.map(point)
        let pt = item.curve == "cubic" ? curve(points,progress) : position(points,progress)
        let radius = item.radius ?? 11
        ctx.setFillColor(NSColor.white.cgColor);ctx.setStrokeColor(c.cgColor);ctx.setLineWidth(5)
        ctx.addEllipse(in:CGRect(x:pt.x-radius,y:pt.y-radius,width:radius*2,height:radius*2));ctx.drawPath(using:.fillStroke)
        ctx.setFillColor(c.cgColor);ctx.fillEllipse(in:CGRect(x:pt.x-4,y:pt.y-4,width:8,height:8))
      } else {
        let r = item.rect!, rect = CGRect(x:r[0],y:r[1],width:r[2],height:r[3])
        if item.kind == "progress" {
          let path = CGPath(roundedRect:rect,cornerWidth:r[3]/2,cornerHeight:r[3]/2,transform:nil)
          ctx.setFillColor(color(item.track_color ?? "#b0d4f5").cgColor);ctx.addPath(path);ctx.fillPath()
          ctx.saveGState();ctx.addPath(path);ctx.clip();ctx.setFillColor(c.cgColor)
          ctx.fill(CGRect(x:r[0],y:r[1],width:r[2]*value(item.keyframes!,t),height:r[3]));ctx.restoreGState()
        } else {
          ctx.setStrokeColor(c.withAlphaComponent(0.5+0.3*sin(t*5)).cgColor);ctx.setLineWidth(item.line_width ?? 6)
          if item.kind == "ellipse" { ctx.strokeEllipse(in:rect) }
          else { ctx.addPath(CGPath(roundedRect:rect,cornerWidth:20,cornerHeight:20,transform:nil));ctx.strokePath() }
        }
      }
    }
    if let index = scene.captions.firstIndex(where: { t >= $0.start && t < $0.end }) {
      if let pos = scene.caption_position {
        let attrs: [NSAttributedString.Key:Any] = [.font:NSFont.systemFont(ofSize:scene.caption_size ?? 29,weight:.semibold),.foregroundColor:color("#1f2933")]
        let text = NSAttributedString(string:scene.captions[index].text,attributes:attrs)
        let size = text.size()
        guard pos[0]+size.width <= Double(width),pos[1]+size.height <= Double(height) else {
          fputs("Caption exceeds canvas; shorten it or revise its position/size.\n",stderr);exit(2)
        }
        text.draw(at:NSPoint(x:pos[0],y:pos[1]))
      }
      if let pos = scene.indicator_position {
        for i in scene.captions.indices {
          ctx.setFillColor((i == index ? color("#0957eb") : NSColor.lightGray.withAlphaComponent(0.45)).cgColor)
          let size = i == index ? 12.0 : 9.0
          ctx.fillEllipse(in:CGRect(x:pos[0]+Double(i)*34,y:pos[1],width:size,height:size))
        }
      }
    }
    NSGraphicsContext.restoreGraphicsState()
    let target = frameDir.appendingPathComponent(String(format:"%04d.png",frame))
    let dest = CGImageDestinationCreateWithURL(target as CFURL,UTType.png.identifier as CFString,1,nil)!
    CGImageDestinationAddImage(dest,ctx.makeImage()!,nil);CGImageDestinationFinalize(dest)
  }
}
print("Rendered \(count) frames at \(width)x\(height)")
