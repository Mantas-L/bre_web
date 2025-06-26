document.addEventListener("DOMContentLoaded", () => {
  fetch("/data")
    .then(response => response.json())
    .then(data => {
      const tableBody = document.querySelector("#data tbody");
      tableBody.innerHTML = "";  // Clear placeholder rows

      for (let k in data) {
        const imageId = data[k]["image_id"];
        const text = data[k]["ocr_text"] || "";

        const row = document.createElement("tr");

        // Image cell
        const imageCell = document.createElement("td");
        const img = document.createElement("img");
        img.src = `/image/${imageId}`;
        img.alt = `Image ${imageId}`;
        img.style.width = "500px";
        img.style.height = "300px";
        imageCell.appendChild(img);

        // Text cell
        const textCell = document.createElement("td");
        textCell.textContent = text;

        row.appendChild(imageCell);
        row.appendChild(textCell);
        tableBody.appendChild(row);
      }
    })
    .catch(error => {
      console.error("Error loading data:", error);
    });
});
