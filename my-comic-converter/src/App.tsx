import React, { useState, useCallback } from "react";
import axios from "axios";

interface FileInfo {
  file: File;
  directory: string;
}

function App() {
  const [conversionID, setConversionID] = useState<string | null>(null);
  const [fileInfos, setFileInfos] = useState<FileInfo[]>([]);

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

      // Log the FormData contents
      for (const [key, value] of formData.entries()) {
        console.log(key, value);
      }

      try {
        const response = await axios.post(
          "http://localhost:5000/convert",
          formData,
          {
            headers: {
              "Content-Type": "multipart/form-data",
            },
            /* possible upload progress bar here */
          }
        );
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
