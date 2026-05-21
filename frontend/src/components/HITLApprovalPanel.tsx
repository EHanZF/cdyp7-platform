import type { Receipt } from "../types/mcp";

interface Props {
  receipt: Receipt;
}

export default function HITLApprovalPanel({
  receipt
}: Props) {
  const approve = () => {
    alert(
      `Approved receipt: ${receipt.receipt_id}`
    );
  };

  return (
    <div className="panel">
      <h2>Human Approval</h2>

      <div>
        Receipt:
        {" "}
        {receipt.receipt_id}
      </div>

      <div>
        Authority:
        {" "}
        {receipt.authority}
      </div>

      <div>
        Tool:
        {" "}
        {receipt.tool}
      </div>

      <button onClick={approve}>
        Approve Receipt
      </button>
    </div>
  );
}