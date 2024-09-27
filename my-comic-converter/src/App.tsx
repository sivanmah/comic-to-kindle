import React, { useState } from "react";
import axios from "axios";

function App() {
  const [files, setFiles] = useState<FileList | null>(null);
  const [conversionID, setConversionID] = useState<string | null>(null);
  const [bookTitle, setBookTitle] = useState<string>("");

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setFiles(event.target.files || null);
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (files) {
      const formData = new FormData();
      for (let i = 0; i < files.length; i++) {
        formData.append("files", files[i]);
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
        setBookTitle(response.data.book_title);
      } catch (error) {
        console.error("Error converting images:", error);
      }
    }
  };

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
        {conversionID && (
          <div>
            <p>Book title: {bookTitle}</p>
            <button onClick={handleDownload}> Download MOBI </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
