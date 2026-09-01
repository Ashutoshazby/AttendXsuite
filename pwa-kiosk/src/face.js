import * as faceapi from "@vladmandic/face-api";

const MODEL_URL = "/models/face-api";
const MATCH_THRESHOLD = 0.5;
const GAP_THRESHOLD = 0.06;
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

export const distance = (left = [], right = []) => {
  let total = 0;
  for (let index = 0; index < Math.min(left.length, right.length); index += 1) {
    const diff = left[index] - right[index];
    total += diff * diff;
  }
  return Math.sqrt(total);
};

export const descriptorFromVideo = async (video) => {
  await loadModels();
  const result = await faceapi
    .detectSingleFace(video, new faceapi.TinyFaceDetectorOptions({ inputSize: 224, scoreThreshold: 0.35 }))
    .withFaceLandmarks(true)
    .withFaceDescriptor();
  if (!result?.descriptor) throw new Error("No clear face detected.");
  return Array.from(result.descriptor);
};

export const recognize = async ({ descriptor, employees }) => {
  const candidates = employees
    .filter((employee) => employee.face_descriptor?.length)
    .map((employee) => ({ employee, distance: distance(descriptor, employee.face_descriptor) }))
    .sort((a, b) => a.distance - b.distance);
  if (!candidates.length) throw new Error("No registered faces found.");
  const best = candidates[0];
  const second = candidates[1];
  if (best.distance > MATCH_THRESHOLD) throw new Error("Unknown face. Attendance not marked.");
  if (second && second.distance - best.distance < GAP_THRESHOLD) throw new Error("Ambiguous face match. Try better lighting.");
  return { employee_id: best.employee.employee_id, employee_name: best.employee.name, confidence: Math.round((1 - best.distance) * 100) };
};
