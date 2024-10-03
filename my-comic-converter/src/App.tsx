import React, { useState, useCallback, useEffect, useRef } from "react";
import axios from "axios";

interface FileInfo {
  file: File;
  directory: string;
}

function App() {
  const [conversionID, setConversionID] = useState<string | null>(null);
  const [fileInfos, setFileInfos] = useState<FileInfo[]>([]);
  const [progress, setProgress] = useState<number | null>(null);
  const [taskID, setTaskID] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);

  const handleInputAreaClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      setError(null);
      const fileList = event.target.files;
      if (fileList) {
        const newFileInfos: FileInfo[] = [];

        for (let i = 0; i < fileList.length; i++) {
          const file = fileList[i];
          const path = file.webkitRelativePath;
          const directory = path.split("/")[0];

          newFileInfos.push({ file, directory });
        }

        setFileInfos((prevFileInfos) => [...prevFileInfos, ...newFileInfos]);
      }
      event.target.value = "";
    },
    []
  );

  const handleSubmit = useCallback(
    async (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      setError(null);

      const formData = new FormData();

      fileInfos.forEach(({ file, directory }) => {
        // Use the full relative path as the key to preserve directory structure
        const key = `${directory}/${file.name}`;
        formData.append(key, file);
      });

      try {
        const response = await axios.post(
          "http://localhost:5000/convert",
          formData,
          {
            headers: {
              "Content-Type": "multipart/form-data",
            },
          }
        );
        setProgress(response.data.progress);
        setTaskID(response.data.task_id);
        setConversionID(response.data.conversion_id);
      } catch (error) {
        if (axios.isAxiosError(error)) {
          if (error.response) {
            setError(error.response.data.error);
          } else if (error.request) {
            setError("No response received from server");
          } else {
            setError("Error setting up the request");
          }
        } else {
          setError("An unexpected error occurred");
        }
      }
    },
    [fileInfos]
  );

  const handleDownload = () => {
    if (conversionID) {
      window.location.href = `http://localhost:5000/download/${conversionID}`;
    }
  };

  useEffect(() => {
    if (taskID) {
      const interval = setInterval(async () => {
        try {
          const response = await axios.get(
            `http://localhost:5000/status/${taskID}`
          );
          setProgress(response.data.progress);
          setConversionID(response.data.conversion_id);
          if (conversionID) {
            clearInterval(interval);
          }
        } catch (error) {
          console.error("Error checking task status:", error);
        }
      }, 1000);
      return () => clearInterval(interval);
    }
  }, [taskID, conversionID]);

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col justify-center items-center">
      <div className="bg-white p-8 rounded-lg shadow-md w-full max-w-md">
        <h1 className="text-3xl font-bold mb-6 text-center text-blue-600">
          Comic2Kindle
        </h1>
        <form
          onSubmit={handleSubmit}
          className="block text-sm font-medium text-gray-700 mb-2"
        >
          <div
            onClick={handleInputAreaClick}
            className="border-2 mb-4 border-dashed border-gray-300 rounded-lg p-6 text-center cursor-pointer hover:border-blue-500 transition-colors duration-300"
          >
            <input
              type="file"
              ref={fileInputRef}
              multiple
              onChange={handleFileChange}
              className="hidden"
              {...({
                webkitdirectory: "",
                directory: "",
                multiple: true,
              } as React.InputHTMLAttributes<HTMLInputElement>)}
            />
            <p className="text-sm text-gray-400">Click here</p>
          </div>
          {error && <p className="text-red-600 text-sm mb-2">{error}</p>}
          <button
            type="submit"
            className={`w-full py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white ${
              fileInfos.length > 0
                ? "bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                : "bg-gray-400 cursor-not-allowed"
            }`}
          >
            Convert
          </button>
        </form>
        {fileInfos.length > 0 && (
          <ul>
            {Array.from(
              new Set(fileInfos.map(({ directory }) => directory))
            ).map((directory) => (
              <li
                className="text-xs mr-1 mb-1 font-semibold inline-block py-1 px-2 rounded-full text-blue-600 bg-blue-200"
                key={directory}
              >
                {directory}
              </li>
            ))}
          </ul>
        )}
        {taskID && (
          <div className="mt-6">
            <p className="text-sm font-medium text-gray-700 mb-2">
              {conversionID ? "Conversion complete!" : "Converting images..."}
            </p>
            <progress
              className="w-full "
              value={progress !== null ? progress : 0}
              max={
                new Set(fileInfos.map(({ directory }) => directory)).size + 1
              }
            ></progress>
          </div>
        )}
        {conversionID && (
          <div className="mt-6">
            <button
              className="w-full py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"
              onClick={handleDownload}
            >
              {" "}
              Download MOBI{" "}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
