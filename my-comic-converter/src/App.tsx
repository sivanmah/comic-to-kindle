import React, { useState, useCallback, useEffect } from "react";
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

  const handleFileChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
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

      const formData = new FormData();

      fileInfos.forEach(({ file, directory }) => {
        // Use the full relative path as the key to preserve directory structure
        const key = `${directory}/${file.name}`;
        formData.append(key, file);
      });

      /*       for (const [key, value] of formData.entries()) {
        console.log(key, value);
      } */

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
        console.error("Error converting images:", error);
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
    <div className="p-20 flex justify-center">
      <div className="">
        <h1 className="py-2">Comic Converter</h1>
        <form onSubmit={handleSubmit} className=" flex flex-row">
          <input
            type="file"
            ref={(input) => {
              if (input) {
                input.setAttribute("webkitdirectory", "");
                input.setAttribute("directory", "");
              }
            }}
            multiple
            onChange={handleFileChange}
            className="block"
          />
          <button
            type="submit"
            className="bg-blue-500 text-white px-4 py-2 rounded"
          >
            Convert
          </button>
        </form>
        {fileInfos.length > 0 && (
          <ul>
            {Array.from(
              new Set(fileInfos.map(({ directory }) => directory))
            ).map((directory) => (
              <li key={directory}>
                <strong>{directory}</strong>
              </li>
            ))}
          </ul>
        )}
        {taskID && (
          <div>
            <p>
              <progress
                value={progress !== null ? progress : 0}
                max={
                  new Set(fileInfos.map(({ directory }) => directory)).size + 1
                }
              ></progress>
            </p>
          </div>
        )}
        {conversionID && (
          <div>
            <button onClick={handleDownload}> Download MOBI </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
