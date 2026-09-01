import * as faceapi from "@vladmandic/face-api";

const MODEL_URL = "/models/face-api";
let modelPromise;

export const loadModels = () => {
  if (!modelPromise) {
    modelPromise = Promise.all([
      faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL),
      faceapi.nets.faceLandmark68TinyNet.loadFromUri(MODEL_URL),
      faceapi.nets.faceRecognitionNet.loadFromUri(MODEL_URL)
    ]);
  }
  return modelPromise;
};

const imageFromBase64 = (base64) =>
  new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("Could not load captured face photo."));
    image.src = base64.startsWith("data:") ? base64 : `data:image/jpeg;base64,${base64}`;
  });

export const createDescriptor = async (base64) => {
  await loadModels();
  const image = await imageFromBase64(base64);
  const result = await faceapi
    .detectSingleFace(image, new faceapi.TinyFaceDetectorOptions({ inputSize: 224, scoreThreshold: 0.35 }))
    .withFaceLandmarks(true)
    .withFaceDescriptor();
  if (!result?.descriptor) {
    throw new Error("No clear face detected. Capture one centered face in good light.");
  }
  return Array.from(result.descriptor);
};

export const distance = (left = [], right = []) => {
  let total = 0;
  for (let index = 0; index < Math.min(left.length, right.length); index += 1) {
    const diff = left[index] - right[index];
    total += diff * diff;
  }
  return Math.sqrt(total);
};
