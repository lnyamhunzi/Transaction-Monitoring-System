// JavaScript for PEP lists management page

document.addEventListener('DOMContentLoaded', function() {
    // Initialize DataTables for the PEP lists table
    const pepListsTable = $('#pepListsTable').DataTable({
        "processing": true,
        "serverSide": true,
        "ajax": {
            "url": "/api/pep/lists",
            "type": "GET",
            "beforeSend": function(request) {
                request.setRequestHeader("Authorization", `Bearer ${localStorage.getItem('admin_token')}`);
            },
            "error": function(xhr, error, thrown) {
                console.error("DataTables AJAX error:", xhr.responseText);
                alert('Error loading PEP data.');
            }
        },
        "columns": [
            { "data": "name" },
            { "data": "country" },
            { "data": "position" },
            { "data": "listed_since" },
            { "data": "actions", "orderable": false, "searchable": false }
        ],
        "paging": true,
        "lengthChange": false,
        "searching": true, // Enable DataTables built-in searching
        "ordering": true,
        "info": true,
        "autoWidth": false,
        "responsive": true
    });

    // Custom search input for DataTables
    const searchInput = document.querySelector('input[placeholder="Search by name or country"]');
    if (searchInput) {
        searchInput.addEventListener('keyup', function() {
            pepListsTable.search(this.value).draw();
        });
    }

    // Event listener for 'Add New PEP' button
    const addNewPEPButton = document.querySelector('.card-body .btn-primary');
    if (addNewPEPButton) {
        addNewPEPButton.addEventListener('click', function() {
            window.location.href = '/sanctions/pep/add';
        });
    }

    // Event listeners for 'View' and 'Edit' buttons (delegated)
    $('#pepListsTable tbody').on('click', '.view-btn', function() {
        const pepId = $(this).data('id');
        window.location.href = `/sanctions/pep/view/${pepId}`;
    });

    $('#pepListsTable tbody').on('click', '.edit-btn', function() {
        const pepId = $(this).data('id');
        window.location.href = `/sanctions/pep/edit/${pepId}`;
    });
});