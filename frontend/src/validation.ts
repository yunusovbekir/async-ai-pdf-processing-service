export interface UploadLimits {
  max_file_size_mb: number;
  max_files_per_upload: number;
}

export interface FileError {
  /** Name of the offending file, or null when the error concerns the whole selection. */
  file: string | null;
  message: string;
}

const isPdf = (file: File): boolean =>
  file.name.toLowerCase().endsWith(".pdf") || file.type === "application/pdf";

export function validateFiles(files: File[], limits: UploadLimits): FileError[] {
  const errors: FileError[] = [];
  const maxBytes = limits.max_file_size_mb * 1024 * 1024;

  if (files.length > limits.max_files_per_upload) {
    errors.push({
      file: null,
      message: `Too many files: ${files.length} selected, at most ${limits.max_files_per_upload} allowed`,
    });
  }
  for (const file of files) {
    if (!isPdf(file)) errors.push({ file: file.name, message: "Not a PDF file" });
    else if (file.size === 0) errors.push({ file: file.name, message: "File is empty" });
    else if (file.size > maxBytes) {
      errors.push({ file: file.name, message: `Larger than ${limits.max_file_size_mb} MB` });
    }
  }
  return errors;
}

const sameFile = (a: File, b: File): boolean =>
  a.name === b.name && a.size === b.size && a.lastModified === b.lastModified;

/** Appends incoming files, skipping exact duplicates (same name, size and lastModified). */
export function mergeFiles(existing: File[], incoming: File[]): File[] {
  const result = [...existing];
  for (const file of incoming) {
    if (!result.some((f) => sameFile(f, file))) result.push(file);
  }
  return result;
}

export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
