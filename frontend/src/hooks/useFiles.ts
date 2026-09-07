import { useCallback, useEffect, useState } from "react";
import { deleteFile, listFiles, uploadFile, type UploadedFileOut } from "../api";

export function useFiles(sessionId: string | null) {
  const [files, setFiles] = useState<UploadedFileOut[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    if (!sessionId) {
      setFiles([]);
      return;
    }
    let cancelled = false;
    listFiles(sessionId).then((f) => {
      if (!cancelled) setFiles(f);
    });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const upload = useCallback(
    async (file: File) => {
      if (!sessionId) return;
      setUploading(true);
      setError(null);
      try {
        const out = await uploadFile(sessionId, file);
        setFiles((prev) => [...prev, out]);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setUploading(false);
      }
    },
    [sessionId],
  );

  const remove = useCallback(
    async (fileId: string) => {
      if (!sessionId) return;
      setFiles((prev) => prev.filter((f) => f.id !== fileId));
      try {
        await deleteFile(sessionId, fileId);
      } catch (e) {
        setError((e as Error).message);
      }
    },
    [sessionId],
  );

  return { files, upload, remove, uploading, error };
}
