
let allRecords = [];

async function loadImportRecords() {
    const response = await fetch("/review-import-bid-records/");
    const result = await response.json();

    allRecords = result.records || [];

    renderStats(allRecords);
    renderTable(allRecords);
}

function renderStats(records) {
    const total = records.length;

    const pending = records.filter(
        record => record.review_status === "pending"
    ).length;

    const approved = records.filter(
        record => record.review_status === "approved"
    ).length;

    const synced = records.filter(
        record => record.review_status === "synced"
    ).length;

    document.getElementById("total-count").innerText = total;
    document.getElementById("pending-count").innerText = pending;
    document.getElementById("approved-count").innerText = approved;
    document.getElementById("synced-count").innerText = synced;
}

function renderTable(records) {
    const tbody = document.getElementById("records-body");

    tbody.innerHTML = "";

    records.forEach(record => {
        const tr = document.createElement("tr");

        const statusClass = getStatusClass(
            record.review_status
        );

        tr.innerHTML = `
            <td>${record.id ?? ""}</td>

            <td>
                <span class="status ${statusClass}">
                    ${record.review_status ?? ""}
                </span>
            </td>

            <td>${record.project_name ?? ""}</td>
            <td>${record.category ?? ""}</td>
            <td>${record.item_name ?? ""}</td>
            <td>${record.quantity ?? ""}</td>
            <td>${record.unit_price ?? ""}</td>
            <td>${record.total_price ?? ""}</td>
            <td>
                <button
                    class="detail-button"
                    onclick="showFeatureDetailById(${record.id})"
                >
                    Detail
                </button>
            </td>

            <td>
                <button class="action-button" onclick="reviewRecord(${record.id}, 'approved')">
                    Approve
                </button>

                <button class="action-button" onclick="reviewRecord(${record.id}, 'rejected')">
                    Reject
                </button>
            </td>
        `;

        tbody.appendChild(tr);
    });
}

function applyFilters() {

    const keyword =
        document
            .getElementById("search-keyword")
            .value
            .toLowerCase();

    const status =
        document
            .getElementById("status-filter")
            .value;

    const filteredRecords =
        allRecords.filter(record => {

            const keywordMatch =

                record.item_name
                    ?.toLowerCase()
                    .includes(keyword)

                ||

                record.category
                    ?.toLowerCase()
                    .includes(keyword)

                ||

                record.project_name
                    ?.toLowerCase()
                    .includes(keyword);

            const statusMatch =

                status === ""

                ||

                record.review_status === status;

            return keywordMatch && statusMatch;
        });

    renderStats(filteredRecords);

    renderTable(filteredRecords);
}

function getStatusClass(status) {
    if (status === "pending") {
        return "status-pending";
    }

    if (status === "approved") {
        return "status-approved";
    }

    if (status === "rejected") {
        return "status-rejected";
    }

    if (status === "synced") {
        return "status-synced";
    }

    return "";
}

async function reviewRecord(recordId, newStatus) {
    // console.log("Review:", recordId, newStatus);
    const response = await fetch(
        `/review-record?record_id=${recordId}&new_status=${newStatus}`,
        {
            method: "POST"
        }
    );

    const result = await response.json();

    console.log("Review result:", result);

    await loadImportRecords();
}



function showFeatureDetail(
    feature
) {

    document
        .getElementById(
            "feature-text"
        )
        .innerText = feature;

    document
        .getElementById(
            "feature-modal"
        )
        .style
        .display = "block";
}



function closeFeatureModal() {

    document
        .getElementById(
            "feature-modal"
        )
        .style
        .display = "none";
}


function getFeatureSummary(feature) {
    if (!feature) {
        return "";
    }

    if (feature.length <= 40) {
        return feature;
    }

    return feature.substring(0, 40) + "...";
}

function showFeatureDetailById(recordId) {
    const record = allRecords.find(
        item => item.id === recordId
    );

    if (!record) {
        alert("Record not found");
        return;
    }

    document.getElementById("modal-item-name").innerText =
        record.item_name ?? "";

    document.getElementById("modal-item-code").innerText =
        record.item_code ?? "";

    document.getElementById("modal-feature-text").innerText =
        record.feature ?? "";

    document.getElementById("feature-modal").style.display =
        "block";
}