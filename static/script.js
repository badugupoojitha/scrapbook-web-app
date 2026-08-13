const createBtn = document.getElementById("createBtn");
const popup = document.getElementById("popup");
const cancelBtn = document.getElementById("cancelBtn");
const scrapbookName = document.getElementById("scrapbookName");
const saveBtn = document.getElementById("saveBtn");
const scrapbookContainer = document.getElementById("scrapbookContainer");

const homePage = document.getElementById("homePage");
const scrapbookPage = document.getElementById("scrapbookPage");
const openedBookName = document.getElementById("openedBookName");
const backBtn = document.getElementById("backBtn");

const addMemoryBtn = document.getElementById("addMemoryBtn");
const memoryPopup = document.getElementById("memoryPopup");
const cancelMemoryBtn = document.getElementById("cancelMemoryBtn");
const saveMemoryBtn = document.getElementById("saveMemoryBtn");
const memoryContainer = document.getElementById("memoryContainer");

let scrapbooks = [];
let currentScrapbook = null;

// Load all scrapbooks on page load
async function loadScrapbooks() {
    const response = await fetch("/api/scrapbooks");
    if (!response.ok) {
        window.location.href = "/login";
        return;
    }
    scrapbooks = await response.json();
    displayScrapbooks();
}

function displayScrapbooks() {
    scrapbookContainer.innerHTML = "";
    scrapbooks.forEach(function(scrapbook) {
        const scrapbookCard = document.createElement("div");
        scrapbookCard.classList.add("scrapbookCard");
        scrapbookCard.style.position = "relative"; // Allows positioning the trash button

        const icon = document.createElement("div");
        icon.textContent = "📖";
        icon.classList.add("bookIcon");

        const title = document.createElement("h3");
        title.textContent = scrapbook.name;

        // Scrapbook Delete Button
        const delBtn = document.createElement("button");
        delBtn.innerHTML = "🗑️";
        delBtn.style.cssText = "position:absolute; top:10px; right:10px; background:none; border:none; cursor:pointer; font-size:14px; padding:0;";
        
        delBtn.addEventListener("click", async function(e) {
            e.stopPropagation(); // Prevents opening the scrapbook when clicking delete
            if (confirm(`Delete "${scrapbook.name}" scrapbook?`)) {
                const res = await fetch(`/api/scrapbooks/${scrapbook.id}`, { method: "DELETE" });
                if (res.ok) loadScrapbooks();
            }
        });

        scrapbookCard.appendChild(delBtn);
        scrapbookCard.appendChild(icon);
        scrapbookCard.appendChild(title);

        scrapbookCard.addEventListener("click", function() {
            openScrapbook(scrapbook);
        });

        scrapbookContainer.appendChild(scrapbookCard);
    });
}

// Open scrapbook page and fetch memories
async function openScrapbook(scrapbook) {
    currentScrapbook = scrapbook;
    homePage.style.display = "none";
    scrapbookPage.style.display = "block";
    openedBookName.textContent = scrapbook.name;

    loadMemories(scrapbook.id);
}

async function loadMemories(scrapbookId) {
    const response = await fetch(`/api/scrapbooks/${scrapbookId}/memories`);
    if (!response.ok) return;

    const memories = await response.json();
    memoryContainer.innerHTML = "";

    memories.forEach(memory => {
        const card = document.createElement("div");
        card.classList.add("memoryCard");
        
        // Add styling for memory cards so they look neat
        card.style.background = "white";
        card.style.borderRadius = "15px";
        card.style.padding = "15px";
        card.style.width = "200px";
        card.style.boxShadow = "0 5px 15px rgba(0,0,0,0.1)";
        card.style.textAlign = "center";

        card.innerHTML = `
            ${memory.image_path ? `<img src="${memory.image_path}" style="width:100%; height:120px; object-fit:cover; border-radius:10px;">` : ''}
            <p style="margin-top:8px;"><strong>${memory.caption}</strong></p>
            <small style="color:#777; display:block; margin:5px 0;">${memory.date}</small>
            <button class="deleteMemoryBtn" data-id="${memory.id}" style="margin-top:8px; padding:6px 12px; background:#d9534f; color:white; border:none; border-radius:8px; cursor:pointer; font-size:13px;">Delete</button>
        `;

        // Handle delete click
        const deleteBtn = card.querySelector(".deleteMemoryBtn");
        deleteBtn.addEventListener("click", async function () {
            if (confirm("Are you sure you want to delete this memory?")) {
                const res = await fetch(`/api/memories/${memory.id}`, {
                    method: "DELETE"
                });

                if (res.ok) {
                    loadMemories(currentScrapbook.id);
                } else {
                    alert("Failed to delete memory.");
                }
            }
        });

        memoryContainer.appendChild(card);
    });
}

// Scrapbook Modals
createBtn.addEventListener("click", () => popup.style.display = "block");
cancelBtn.addEventListener("click", () => popup.style.display = "none");

saveBtn.addEventListener("click", async function () {
    const name = scrapbookName.value.trim();
    if (!name) {
        alert("Please enter a scrapbook name.");
        return;
    }

    const response = await fetch("/api/scrapbooks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name })
    });

    const scrapbook = await response.json();
    if (!response.ok) {
        alert(scrapbook.error || "Could not create scrapbook.");
        return;
    }

    scrapbooks.push(scrapbook);
    displayScrapbooks();
    popup.style.display = "none";
    scrapbookName.value = "";
});

// Memory Modals
backBtn.addEventListener("click", function () {
    scrapbookPage.style.display = "none";
    homePage.style.display = "block";
    currentScrapbook = null;
});

addMemoryBtn.addEventListener("click", () => memoryPopup.style.display = "block");
cancelMemoryBtn.addEventListener("click", () => memoryPopup.style.display = "none");

// Save Memory with FormData (Image Upload)
saveMemoryBtn.addEventListener("click", async function () {
    if (!currentScrapbook) return;

    const fileInput = document.getElementById("memoryImage");
    const captionInput = document.getElementById("memoryCaption");
    const dateInput = document.getElementById("memoryDate");

    const formData = new FormData();
    if (fileInput.files[0]) {
        formData.append("image", fileInput.files[0]);
    }
    formData.append("caption", captionInput.value);
    formData.append("date", dateInput.value);

    const response = await fetch(`/api/scrapbooks/${currentScrapbook.id}/memories`, {
        method: "POST",
        body: formData
    });

    if (response.ok) {
        memoryPopup.style.display = "none";
        captionInput.value = "";
        dateInput.value = "";
        fileInput.value = "";
        loadMemories(currentScrapbook.id);
    } else {
        alert("Failed to save memory.");
    }
});

loadScrapbooks();