export async function prepareImage(file: File): Promise<File> {
  if (file.size > 15 * 1024 * 1024) throw new Error("Photos must be 15 MB or smaller.");
  if (!/\.(jpe?g|png|webp|heic|heif)$/i.test(file.name))
    throw new Error("Choose a JPG, PNG, WebP, HEIC or HEIF photo.");
  let source: Blob = file;
  if (/\.(heic|heif)$/i.test(file.name)) {
    const { default: convert } = await import("heic2any");
    const result = await convert({ blob: file, toType: "image/jpeg", quality: 0.9 });
    source = Array.isArray(result) ? result[0] : result;
  }
  const bitmap = await createImageBitmap(source, { imageOrientation: "from-image" });
  const scale = Math.min(1, 2048 / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Photo processing is not available.");
  ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  const blob = await new Promise<Blob>((resolve, reject) =>
    canvas.toBlob(
      (b) => (b ? resolve(b) : reject(new Error("Could not prepare this photo."))),
      "image/jpeg",
      0.9,
    ),
  );
  return new File([blob], file.name.replace(/\.[^.]+$/, ".jpg"), { type: "image/jpeg" });
}
