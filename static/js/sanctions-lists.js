// JavaScript for sanctions lists management page

document.addEventListener('DOMContentLoaded', function() {
    // Initialize DataTables for the sanctions lists table
    const sanctionsListsTable = $('#sanctionsListsTable').DataTable({
        "processing": true,
        "serverSide": true,
        "ajax": {
            "url": "/api/sanctions/lists",
            "type": "GET",
            "beforeSend": function(request) {
                request.setRequestHeader("Authorization", `Bearer ${localStorage.getItem('admin_token')}`);
            },
            "error": function(xhr, error, thrown) {
                console.error("DataTables AJAX error:", xhr.responseText);
                alert('Error loading sanctions data.');
            }
        },
        "columns": [
            { "data": "list_name" },
            { "data": "entity_name" },
            { "data": "entity_type" },
            { "data": "nationality" },
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
    const searchInput = document.querySelector('input[placeholder="Search by list name"]');
    if (searchInput) {
        searchInput.addEventListener('keyup', function() {
            sanctionsListsTable.search(this.value).draw();
        });
    }

    // Event listener for 'Add New List' button
    const addNewListButton = document.querySelector('.card-body .btn-primary');
    if (addNewListButton) {
        addNewListButton.addEventListener('click', function() {
            window.location.href = '/sanctions/lists/add';
        });
    }

    // Event listeners for 'View' and 'Edit' buttons (delegated)
    $('#sanctionsListsTable tbody').on('click', '.view-btn', function() {
        const listId = $(this).data('id');
        window.location.href = `/sanctions/lists/view/${listId}`;
    });

    $('#sanctionsListsTable tbody').on('click', '.edit-btn', function() {
        const listId = $(this).data('id');
        window.location.href = `/sanctions/lists/edit/${listId}`;
    });
});